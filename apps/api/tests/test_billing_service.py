"""services/billing.py metering + entitlement — the pure Redis/Postgres half.

fakeredis for the counter/cache, in-memory SQLite (conftest) for the cold-warm
site->account lookup. No Stripe here (that's test_billing_router / the mocked
SDK); these lock the money-math: counter, quota derivation, soft-cap flags, and
the read-time lapsed-trial downgrade.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.exceptions import ValidationError
from app.models.tables import Account
from app.services import billing

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _account(plan: str = "pro", status: str = "active", trial_ends_at=None) -> Account:
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


# --- entitlement / quota -------------------------------------------------
def test_effective_plan_active_subscription() -> None:
    assert billing.effective_plan(_account(plan="pro", status="active"), NOW) == "pro"


def test_effective_plan_past_due_keeps_serving() -> None:
    # Failed payment must not yank access mid-cycle (§10).
    assert billing.effective_plan(_account(plan="business", status="past_due"), NOW) == "business"


def test_effective_plan_trial_in_window() -> None:
    acc = _account(plan="pro", status="trialing", trial_ends_at=NOW + timedelta(days=2))
    assert billing.effective_plan(acc, NOW) == "pro"


def test_effective_plan_lapsed_trial_downgrades_to_free() -> None:
    # Card-free trial ended, never subscribed -> free, with NO webhook involved.
    acc = _account(plan="pro", status="trialing", trial_ends_at=NOW - timedelta(days=1))
    assert billing.effective_plan(acc, NOW) == "free"


def test_effective_plan_canceled_is_free() -> None:
    assert billing.effective_plan(_account(plan="pro", status="canceled"), NOW) == "free"


def test_quota_for_known_and_unknown() -> None:
    assert billing.quota_for("pro") == 100_000
    assert billing.quota_for("mystery") == billing.quota_for("free") == 10_000


def test_usage_status_thresholds() -> None:
    assert billing.usage_status(0, 100) == "ok"
    assert billing.usage_status(79, 100) == "ok"
    assert billing.usage_status(80, 100) == "warning"  # 80%
    assert billing.usage_status(100, 100) == "over"  # 100%
    assert billing.usage_status(150, 100) == "over"


def test_over_hard_ceiling_only_past_3x() -> None:
    assert billing.over_hard_ceiling(299_999, 100_000) is False  # soft cap still ingests
    assert billing.over_hard_ceiling(300_000, 100_000) is True  # runaway guard


async def test_usage_summary_shape_and_pct() -> None:
    redis = await _fake_redis()
    acc = _account(plan="pro", status="active")
    await redis.set(billing.usage_key(acc.id, NOW), 80_000)
    summary = await billing.usage_summary(redis, acc, NOW)
    assert summary == {
        "plan": "pro",
        "quota": 100_000,
        "used": 80_000,
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


# --- Stripe price mapping ------------------------------------------------
def test_price_id_resolves_and_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_m")
    monkeypatch.setattr(settings, "stripe_price_business_annual", "price_biz_y")
    assert billing._price_id("pro", "monthly") == "price_pro_m"
    assert billing._price_id("business", "annual") == "price_biz_y"
    with pytest.raises(ValidationError):
        billing._price_id("enterprise", "monthly")  # unknown tier


def test_tier_for_price_ignores_empty_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unconfigured (empty) price ids must never match an unknown incoming id.
    monkeypatch.setattr(settings, "stripe_price_pro", "")
    monkeypatch.setattr(settings, "stripe_price_business", "price_biz_m")
    assert billing._tier_for_price("price_biz_m") == "business"
    assert billing._tier_for_price("") == "free"
    assert billing._tier_for_price("price_unknown") == "free"


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
        "items": {"data": [{"price": {"id": "price_pro_m"}}]},
    }
    obj.update(obj_over)
    return {"type": etype, "data": {"object": obj}}


async def test_subscription_updated_grants_entitlement(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_m")
    acc_id = await _seed_account(session_factory, plan="free", status="trialing")
    event = _sub_event("customer.subscription.updated", acc_id)
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        sub = await billing._subscription_for_account(s, acc_id)
        assert acc.plan == "pro" and acc.status == "active"
        assert sub.stripe_customer_id == "cus_1" and sub.stripe_price_id == "price_pro_m"
        assert sub.stripe_subscription_id == "sub_1"


async def test_period_end_read_from_item_when_top_level_absent(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stripe API 2025-03-31.basil+ drops `current_period_end` from the sub object
    # and carries it on the subscription item instead. Read the item.
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_m")
    acc_id = await _seed_account(session_factory, plan="free", status="trialing")
    event = _sub_event(
        "customer.subscription.updated",
        acc_id,
        current_period_end=None,  # absent at the top level (new API shape)
        items={"data": [{"price": {"id": "price_pro_m"}, "current_period_end": 1_793_000_000}]},
    )
    async with session_factory() as s:
        await billing.apply_subscription_event(s, event)
        await s.commit()
    async with session_factory() as s:
        sub = await billing._subscription_for_account(s, acc_id)
        # SQLite returns a naive datetime; Postgres a UTC-aware one — normalize.
        got = sub.current_period_end
        if got.tzinfo is None:
            got = got.replace(tzinfo=UTC)
        assert got == datetime.fromtimestamp(1_793_000_000, tz=UTC)


async def test_subscription_deleted_downgrades_to_free(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_m")
    acc_id = await _seed_account(session_factory, plan="pro", status="active")
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


async def test_payment_failed_sets_past_due_keeps_plan(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_m")
    acc_id = await _seed_account(session_factory, plan="pro", status="active")
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
        assert acc.status == "past_due" and acc.plan == "pro"  # data never yanked


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


async def test_trial_will_end_is_noop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    acc_id = await _seed_account(session_factory, plan="pro", status="trialing")
    async with session_factory() as s:
        await billing.apply_subscription_event(
            s, _sub_event("customer.subscription.trial_will_end", acc_id)
        )
        await s.commit()
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        assert acc.status == "trialing"  # unchanged
