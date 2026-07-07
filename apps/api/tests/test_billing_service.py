"""services/billing.py metering + entitlement — the pure Redis/Postgres half.

fakeredis for the counter/cache, in-memory SQLite (conftest) for the webhook
state machine + usage-push. No live Stripe here (the SDK call is monkeypatched);
these lock the money-math: the account-wide counter, the free/metered
entitlement split, the >1k free lock, the one-trial-per-account rule, the
delta-based usage push, and the read-time lapsed-trial downgrade (Phase 14).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import fakeredis.aioredis
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import FREE_MONTHLY_VIEWS, settings
from app.core.exceptions import AccountLockedError, UpgradeRequiredError
from app.models.tables import Account, Subscription
from app.services import billing

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _account(plan: str = "metered", status: str = "active", trial_ends_at=None) -> Account:
    return Account(
        email="a@example.com",
        username="a",
        plan=plan,
        status=status,
        trial_ends_at=trial_ends_at,
    )


async def _fake_redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# --- counter -------------------------------------------------------------
async def test_record_usage_increments_month_key_and_sets_ttl() -> None:
    redis = await _fake_redis()
    acc_id = UUID(int=1)
    await billing.record_usage(redis, acc_id, NOW)
    await billing.record_usage(redis, acc_id, NOW)
    assert await billing.get_usage(redis, acc_id, NOW) == 2
    ttl = await redis.ttl(billing.usage_key(acc_id, NOW))
    assert 0 < ttl <= 45 * 24 * 3600
    await redis.aclose()


async def test_usage_key_is_month_scoped() -> None:
    acc_id = UUID(int=2)
    july = billing.usage_key(acc_id, NOW)
    august = billing.usage_key(acc_id, NOW.replace(month=8))
    assert july.endswith(":202607") and august.endswith(":202608")
    assert july != august  # a new month starts a fresh counter


async def test_get_usage_zero_when_unset() -> None:
    redis = await _fake_redis()
    assert await billing.get_usage(redis, UUID(int=3), NOW) == 0
    await redis.aclose()


# --- entitlement (free / metered) ----------------------------------------
def test_effective_plan_active_subscription_is_metered() -> None:
    assert billing.effective_plan(_account(status="active"), NOW) == "metered"


def test_effective_plan_past_due_keeps_serving() -> None:
    # Failed payment must not yank access mid-cycle (§10).
    assert billing.effective_plan(_account(status="past_due"), NOW) == "metered"


def test_effective_plan_trial_in_window_is_metered() -> None:
    acc = _account(status="trialing", trial_ends_at=NOW + timedelta(days=2))
    assert billing.effective_plan(acc, NOW) == "metered"


def test_effective_plan_lapsed_trial_downgrades_to_free() -> None:
    # Card-free trial ended, never subscribed -> free, with NO webhook involved.
    acc = _account(status="trialing", trial_ends_at=NOW - timedelta(days=1))
    assert billing.effective_plan(acc, NOW) == "free"


def test_effective_plan_canceled_is_free() -> None:
    assert billing.effective_plan(_account(status="canceled"), NOW) == "free"


def test_effective_plan_new_account_is_free() -> None:
    assert billing.effective_plan(_account(plan="free", status="free"), NOW) == "free"


# --- the >1k free lock ---------------------------------------------------
def test_free_account_locked_only_past_the_free_limit() -> None:
    free = _account(plan="free", status="free")
    assert billing.is_locked(free, FREE_MONTHLY_VIEWS, NOW) is False  # exactly at limit → ok
    assert billing.is_locked(free, FREE_MONTHLY_VIEWS + 1, NOW) is True  # one over → locked


def test_metered_account_never_locked() -> None:
    paying = _account(status="active")
    assert billing.is_locked(paying, FREE_MONTHLY_VIEWS * 100, NOW) is False


def test_trial_expiry_relocks_over_limit_account() -> None:
    # An expired trial falls back to free; if it's over the free limit it re-locks.
    lapsed = _account(status="trialing", trial_ends_at=NOW - timedelta(days=1))
    assert billing.is_locked(lapsed, FREE_MONTHLY_VIEWS + 5, NOW) is True


def test_usage_status_thresholds() -> None:
    warn_at = int(FREE_MONTHLY_VIEWS * 0.8)
    assert billing.usage_status("free", 0) == "ok"
    assert billing.usage_status("free", warn_at - 1) == "ok"
    assert billing.usage_status("free", warn_at) == "warning"
    assert billing.usage_status("free", FREE_MONTHLY_VIEWS) == "warning"  # at limit, not over
    assert billing.usage_status("free", FREE_MONTHLY_VIEWS + 1) == "locked"
    assert billing.usage_status("metered", FREE_MONTHLY_VIEWS * 50) == "ok"  # paying never warns


async def test_ensure_not_locked_raises_for_over_limit_free() -> None:
    redis = await _fake_redis()
    acc = _account(plan="free", status="free")
    await redis.set(billing.usage_key(acc.id, NOW), FREE_MONTHLY_VIEWS + 1)
    with pytest.raises(AccountLockedError):
        await billing.ensure_not_locked(redis, acc, NOW)
    await redis.aclose()


async def test_ensure_not_locked_passes_for_paying() -> None:
    redis = await _fake_redis()
    acc = _account(status="active")
    await redis.set(billing.usage_key(acc.id, NOW), FREE_MONTHLY_VIEWS * 10)
    await billing.ensure_not_locked(redis, acc, NOW)  # must not raise
    await redis.aclose()


async def test_usage_summary_shape_and_pct() -> None:
    redis = await _fake_redis()
    acc = _account(plan="free", status="free")
    await redis.set(billing.usage_key(acc.id, NOW), 800)
    summary = await billing.usage_summary(redis, acc, NOW)
    assert summary == {
        "plan": "free",
        "quota": FREE_MONTHLY_VIEWS,
        "used": 800,
        "pct": 80.0,
        "status": "warning",
    }
    await redis.aclose()


# --- site -> account resolution (Redis-only) ----------------------------
async def test_cache_site_account_round_trips() -> None:
    redis = await _fake_redis()
    acc_id = UUID(int=42)
    await billing.cache_site_account(redis, "pub9", acc_id)
    assert await billing.cached_account_id(redis, "pub9") == acc_id
    await redis.aclose()


async def test_cached_account_id_unknown_site_is_none() -> None:
    redis = await _fake_redis()
    assert await billing.cached_account_id(redis, "nope") is None
    await redis.aclose()


# --- Stripe price mapping (single metered price) -------------------------
def test_tier_for_price_maps_metered_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    assert billing._tier_for_price("price_metered") == "metered"
    assert billing._tier_for_price("price_other") == "free"


def test_tier_for_price_empty_config_never_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "")
    assert billing._tier_for_price("") == "free"  # unconfigured must not match empty


# --- one trial per account -----------------------------------------------
def test_has_used_trial_tracks_trial_ends_at() -> None:
    assert (
        billing._has_used_trial(_account(plan="free", status="free", trial_ends_at=None)) is False
    )
    assert billing._has_used_trial(_account(trial_ends_at=NOW - timedelta(days=1))) is True


# --- usage push to Stripe (delta, no double-count) -----------------------
async def _seed_metered_sub(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    async with session_factory() as s:
        acc = Account(email="p@e.com", username="p", plan="metered", status="active")
        s.add(acc)
        await s.flush()
        s.add(Subscription(account_id=acc.id, stripe_customer_id="cus_x", status="active"))
        await s.commit()
        return acc.id


async def test_report_usage_pushes_delta_and_never_double_counts(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_metered_sub(session_factory)
    redis = await _fake_redis()
    pushes: list[tuple[str, int]] = []

    async def fake_push(customer_id: str, value: int) -> None:
        pushes.append((customer_id, value))

    monkeypatch.setattr(billing, "_push_meter_event", fake_push)

    await redis.set(billing.usage_key(acc_id, NOW), 5_000)
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 1
    assert pushes == [("cus_x", 5_000)]  # full counter on first push

    # Re-run with no new usage → nothing to push (delta 0).
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 0
    assert len(pushes) == 1

    # More usage → only the delta is pushed.
    await redis.set(billing.usage_key(acc_id, NOW), 5_300)
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 1
    assert pushes[-1] == ("cus_x", 300)
    await redis.aclose()


async def test_report_usage_marker_is_durable_across_redis_loss(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The "already reported" high-water mark lives in Postgres, so a Redis flush
    # (counter reset to 0) can't make the next run re-push a whole month — that
    # would double-bill via Stripe's additive meter (§9). Worst case is
    # under-billing (delta ≤ 0 → skip), never over.
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_metered_sub(session_factory)
    redis = await _fake_redis()
    pushes: list[tuple[str, int]] = []

    async def fake_push(customer_id: str, value: int) -> None:
        pushes.append((customer_id, value))

    monkeypatch.setattr(billing, "_push_meter_event", fake_push)

    await redis.set(billing.usage_key(acc_id, NOW), 5_000)
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 1
    assert pushes == [("cus_x", 5_000)]

    # Simulate a Redis flush: the ephemeral counter is gone, the Postgres marker
    # is NOT. The re-run must NOT re-push (would double-bill).
    await redis.delete(billing.usage_key(acc_id, NOW))
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 0
    assert len(pushes) == 1  # no phantom re-push of the whole month

    # The durable marker survived in Postgres.
    async with session_factory() as s:
        sub = await s.scalar(select(Subscription))
        assert sub.metered_usage_reported == 5_000
        assert sub.metered_usage_period == f"{NOW:%Y%m}"
    await redis.aclose()


async def test_report_usage_skips_free_accounts(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    async with session_factory() as s:
        acc = Account(email="f@e.com", username="f", plan="free", status="free")
        s.add(acc)
        await s.flush()
        s.add(Subscription(account_id=acc.id, stripe_customer_id="cus_f", status="canceled"))
        await s.commit()
        acc_id = acc.id
    redis = await _fake_redis()
    monkeypatch.setattr(billing, "_push_meter_event", _fail_if_called)
    await redis.set(billing.usage_key(acc_id, NOW), 9_999)
    async with session_factory() as s:
        assert await billing.report_usage_to_stripe(s, redis, NOW) == 0  # free → not metered
    await redis.aclose()


async def _fail_if_called(customer_id: str, value: int) -> None:
    raise AssertionError("must not push usage for a free account")


# --- webhook state machine ----------------------------------------------
async def _seed_account(session_factory: async_sessionmaker[AsyncSession], **over: object) -> UUID:
    async with session_factory() as s:
        acc = Account(email="w@example.com", username="w", **over)
        s.add(acc)
        await s.commit()
        return acc.id


def _sub_event(etype: str, account_id: UUID, **obj_over: object) -> dict:
    obj = {
        "id": "sub_1",
        "customer": "cus_1",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_end": 1_793_000_000,
        "metadata": {"account_id": str(account_id)},
        "items": {"data": [{"price": {"id": "price_metered"}}]},
    }
    obj.update(obj_over)
    return {"type": etype, "data": {"object": obj}}


async def test_subscription_updated_grants_metered_entitlement(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_account(session_factory, plan="free", status="free")
    event = _sub_event("customer.subscription.updated", acc_id)
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        sub = await billing._subscription_for_account(s, acc_id)
        assert acc.plan == "metered" and acc.status == "active"
        assert sub.stripe_customer_id == "cus_1" and sub.stripe_price_id == "price_metered"
        assert sub.stripe_subscription_id == "sub_1"


async def test_trialing_webhook_stamps_trial_ends_at(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The trial start is recorded so the account can't get a second one.
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_account(session_factory, plan="free", status="free")
    trial_end = int((NOW + timedelta(days=7)).timestamp())
    event = _sub_event(
        "customer.subscription.created", acc_id, status="trialing", trial_end=trial_end
    )
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        assert acc.status == "trialing"
        assert acc.trial_ends_at is not None
        assert billing._has_used_trial(acc) is True  # a second checkout gets no trial


async def test_period_end_read_from_item_when_top_level_absent(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stripe API 2025-03-31.basil+ drops `current_period_end` from the sub object
    # and carries it on the subscription item instead. Read the item.
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_account(session_factory, plan="free", status="free")
    event = _sub_event(
        "customer.subscription.updated",
        acc_id,
        current_period_end=None,  # absent at the top level (new API shape)
        items={"data": [{"price": {"id": "price_metered"}, "current_period_end": 1_793_000_000}]},
    )
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)
        await s.commit()
    async with session_factory() as s:
        sub = await billing._subscription_for_account(s, acc_id)
        got = sub.current_period_end
        if got.tzinfo is None:
            got = got.replace(tzinfo=UTC)
        assert got == datetime.fromtimestamp(1_793_000_000, tz=UTC)


async def test_subscription_deleted_downgrades_to_free(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_account(session_factory, plan="free", status="free")
    async with session_factory() as s:
        await billing.apply_subscription_event(
            s, _sub_event("customer.subscription.updated", acc_id)
        )
        await s.commit()
    async with session_factory() as s:
        await billing.apply_subscription_event(
            s, _sub_event("customer.subscription.deleted", acc_id)
        )
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        assert acc.plan == "free" and acc.status == "canceled"


async def test_payment_failed_sets_past_due_keeps_serving(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_metered", "price_metered")
    acc_id = await _seed_account(session_factory, plan="free", status="free")
    async with session_factory() as s:
        await billing.apply_subscription_event(
            s, _sub_event("customer.subscription.updated", acc_id)
        )
        await s.commit()
    # Invoice event carries no metadata -> resolved via stripe_customer_id.
    invoice = {
        "type": "invoice.payment_failed",
        "data": {"object": {"customer": "cus_1", "metadata": {}}},
    }
    async with session_factory() as s:
        await billing.apply_subscription_event(s, invoice)
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        assert acc.status == "past_due" and acc.plan == "metered"  # data never yanked


async def test_unattributable_event_is_noop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # No metadata + unknown customer -> can't map to an account -> no crash.
    event = {
        "type": "customer.subscription.updated",
        "data": {"object": {"customer": "cus_unknown", "metadata": {}}},
    }
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)  # must not raise
        await s.commit()


# --- Phase 11: paid-tier city gate -----------------------------------------
def test_require_dimension_access_gates_city_for_free() -> None:
    free = _account(plan="free", status="free")
    with pytest.raises(UpgradeRequiredError):
        billing.require_dimension_access(free, "city", NOW)


def test_require_dimension_access_allows_paid_city() -> None:
    paid = _account(status="active")  # metered → paying
    billing.require_dimension_access(paid, "city", NOW)  # must not raise


def test_require_dimension_access_ignores_free_dimensions() -> None:
    free = _account(plan="free", status="free")
    billing.require_dimension_access(free, "country", NOW)  # not gated, no raise
    billing.require_dimension_access(free, "language", NOW)
