"""Billing & usage metering — the money surface (CLAUDE.md §9/§10).

Split of truth:
  - **Redis** owns *usage* — a per-account monthly pageview counter
    ``usage:{account_id}:{YYYYMM}`` incremented on the ingest hot path.
  - **Stripe** owns *entitlement* — what tier an account is on. It flips
    ``account.plan``/``account.status`` **only** via verified webhooks
    (see the Stripe section below), never from a Checkout redirect.
  - **Postgres** is the durable mirror (`accounts`, `subscriptions`).

This module holds the pure metering/entitlement logic (Redis + Postgres, no
HTTP). The Stripe SDK calls live in the same module but in their own section so
the metering half stays trivially unit-testable with fakeredis.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import HARD_CEILING_MULTIPLE, PLAN_QUOTAS, settings
from app.core.exceptions import BillingError, UpgradeRequiredError, ValidationError
from app.models.tables import Account, Subscription
from app.services.email import send_email

logger = logging.getLogger("flowly.billing")

# The free tier is both the entry plan and the fallback when entitlement lapses
# (expired trial with no sub, or a canceled subscription).
FREE_PLAN = "free"

# Audience dimensions gated to paying accounts (Phase 11). City comes from the
# GeoLite2-City lookup; it's the first premium report. Enforced at read time on
# every path that serves it (dashboard, public share, CSV export).
PAID_AUDIENCE_DIMENSIONS = frozenset({"city"})

# Usage keys are month-scoped, so a ~45-day TTL lets a finished month self-clean
# a couple of weeks after it ends while the current month always survives.
_USAGE_TTL_SECONDS = 45 * 24 * 3600

# Soft-cap warning threshold (fraction of quota) surfaced to the dashboard.
_WARNING_FRACTION = 0.8


# --- Usage metering (Redis) ----------------------------------------------
def usage_key(account_id: UUID, now: datetime) -> str:
    """Redis counter key for an account's pageviews in `now`'s calendar month."""
    return f"usage:{account_id}:{now:%Y%m}"


async def record_usage(redis: Redis, account_id: UUID, now: datetime) -> None:
    """Count one pageview toward the account's monthly usage (INCR + refresh TTL).

    Pipelined into one round trip. Called best-effort on the ingest hot path
    *after* the durable XADD, so a Redis hiccup here never breaks `/collect`.
    """
    key = usage_key(account_id, now)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _USAGE_TTL_SECONDS)
    await pipe.execute()


async def get_usage(redis: Redis, account_id: UUID, now: datetime) -> int:
    """Pageviews recorded for the account this calendar month (0 if none)."""
    raw = await redis.get(usage_key(account_id, now))
    return int(raw) if raw else 0


# --- site_id -> account resolution (Redis-only) ---------------------------
# The mapping is immutable (a site never changes owner), so it's cached in Redis
# without expiry, written once at site creation (`cache_site_account`). The hot
# path reads it Redis-only — it never touches Postgres (§9).
def _site_account_key(site_id: str) -> str:
    return f"site:{site_id}"


async def cached_account_id(redis: Redis, site_id: str) -> UUID | None:
    """Redis-only site->account lookup — no Postgres, safe on the hot path."""
    cached = await redis.get(_site_account_key(site_id))
    return UUID(cached) if cached else None


async def cache_site_account(redis: Redis, site_id: str, account_id: UUID) -> None:
    """Persist the immutable `site:{site_id} -> account_id` mapping in Redis."""
    await redis.set(_site_account_key(site_id), str(account_id))


async def uncache_site_account(redis: Redis, site_id: str) -> None:
    """Drop a site's cached `site:{site_id} -> account_id` map (site deletion)."""
    await redis.delete(_site_account_key(site_id))


async def meter_pageview(redis: Redis, site_id: str, now: datetime) -> None:
    """Count one counted pageview toward its account's monthly usage (hot path).

    Redis-only account resolution keeps `/collect` off Postgres (§9): the
    site->account map is written once at site creation. If it isn't present
    (the best-effort creation-time write was lost), the increment is skipped
    rather than blocking the hot path. Callers wrap this best-effort; a Redis
    error is swallowed.

    NB: the absolute hard ceiling is NOT enforced here — that would need
    `account.plan` (a Postgres read) per event. Burst cost is already bounded by
    the per-site rate limit (Phase 3); `over_hard_ceiling` is available for a
    future async/worker sweep. The hot path only meters.
    """
    account_id = await cached_account_id(redis, site_id)
    if account_id is None:
        logger.debug("usage metering skipped: no site->account map for %s", site_id)
        return
    await record_usage(redis, account_id, now)


# --- Entitlement / quota (read-time, derived) ----------------------------
def _as_utc(dt: datetime) -> datetime:
    """Treat a naive stored timestamp as UTC (§4 — all stored time is UTC).

    Postgres/asyncpg returns tz-aware datetimes for our timestamptz columns; this
    guards the rare driver (or SQLite) that hands back a naive value, so the
    entitlement comparison can never raise on mixed awareness.
    """
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def effective_plan(account: Account, now: datetime) -> str:
    """The tier the account is actually entitled to right now.

    Entitlement is derived, never separately stored: an active or past-due
    subscription (past-due keeps serving — §10) grants `account.plan`; an
    in-window trial grants `account.plan`; anything else — a lapsed card-free
    trial or a canceled subscription — falls back to `free`. This is why a
    never-paid expired trial needs no webhook to "downgrade" it.
    """
    if account.status in ("active", "past_due"):
        return account.plan
    if account.status == "trialing" and (
        account.trial_ends_at is None or _as_utc(account.trial_ends_at) > now
    ):
        return account.plan
    return FREE_PLAN


def require_dimension_access(account: Account, dimension: str, now: datetime) -> None:
    """Raise `UpgradeRequiredError` if `dimension` is paid-only and the account's
    effective plan is free. A no-op for free dimensions or paying accounts.

    Called from every read path that serves audience breakdowns (authed stats,
    public share, CSV export) so the gate isn't UI-only (§9)."""
    if dimension in PAID_AUDIENCE_DIMENSIONS and effective_plan(account, now) == FREE_PLAN:
        raise UpgradeRequiredError()


def quota_for(plan: str) -> int:
    """Monthly pageview quota for a plan (unknown plans fall back to free)."""
    return PLAN_QUOTAS.get(plan, PLAN_QUOTAS[FREE_PLAN])


def over_hard_ceiling(used: int, quota: int) -> bool:
    """True past the absolute drop ceiling (a runaway/abuse guard, not the quota).

    Below this the soft cap keeps ingesting (§9: never drop a paying customer's
    data); only this pathological threshold drops events.
    """
    return used >= quota * HARD_CEILING_MULTIPLE


def usage_status(used: int, quota: int) -> str:
    """`ok` | `warning` (>=80%) | `over` (>=100%) — drives the dashboard nudge."""
    if quota <= 0 or used >= quota:
        return "over"
    if used >= quota * _WARNING_FRACTION:
        return "warning"
    return "ok"


async def usage_summary(
    redis: Redis, account: Account, now: datetime | None = None
) -> dict[str, object]:
    """The `/billing/usage` payload: plan, quota, used, pct, status.

    Read-time only — the hot path never computes this. `pct` is rounded so the
    UI never shows a float artifact (§4).
    """
    now = now or datetime.now(UTC)
    plan = effective_plan(account, now)
    quota = quota_for(plan)
    used = await get_usage(redis, account.id, now)
    pct = round(used / quota * 100, 1) if quota > 0 else 100.0
    return {
        "plan": plan,
        "quota": quota,
        "used": used,
        "pct": pct,
        "status": usage_status(used, quota),
    }


# --- Stripe (entitlement) -------------------------------------------------
# All entitlement (account.plan/status) is granted ONLY by the webhook handlers
# below, from a signature-verified event — never from a Checkout redirect (§10).
_INTERVALS = ("monthly", "annual")


def _configure_stripe() -> None:
    """Point the SDK at our secret key (cheap; idempotent per process)."""
    stripe.api_key = settings.stripe_secret_key


def _price_id(tier: str, interval: str) -> str:
    """Resolve a (tier, interval) to its configured Stripe price id, or 422."""
    prices = {
        ("pro", "monthly"): settings.stripe_price_pro,
        ("pro", "annual"): settings.stripe_price_pro_annual,
        ("business", "monthly"): settings.stripe_price_business,
        ("business", "annual"): settings.stripe_price_business_annual,
    }
    price = prices.get((tier, interval))
    if not price:
        raise ValidationError("Unknown plan or billing interval.")
    return price


def _tier_for_price(price_id: str) -> str:
    """Reverse a Stripe price id to its plan tier (unknown/empty -> free)."""
    mapping = {
        settings.stripe_price_pro: "pro",
        settings.stripe_price_pro_annual: "pro",
        settings.stripe_price_business: "business",
        settings.stripe_price_business_annual: "business",
    }
    mapping.pop("", None)  # empty (unconfigured) ids must never match
    return mapping.get(price_id, FREE_PLAN)


async def create_checkout_session(
    session: AsyncSession, account: Account, tier: str, interval: str
) -> str:
    """A Stripe Checkout URL for `account` to subscribe to (tier, interval).

    `client_reference_id` + subscription metadata carry the account id so the
    webhook can attribute the resulting subscription regardless of event order.
    During an in-window trial we pass `trial_end` so Stripe neither starts a
    second trial nor charges early (§10); a lapsed trial subscribes immediately.

    An account that already has an active/past-due subscription is sent to the
    Customer Portal instead — re-running Checkout would mint a *second* live
    Stripe subscription (double billing). Where we already know the account's
    Stripe customer, it's reused so Checkout can't create a duplicate customer.
    """
    _configure_stripe()
    price = _price_id(tier, interval)
    if account.status in ("active", "past_due"):
        raise BillingError(
            "You already have an active subscription. Use the customer portal to change plans."
        )
    sub_data: dict[str, Any] = {"metadata": {"account_id": str(account.id)}}
    now = datetime.now(UTC)
    if account.trial_ends_at is not None and account.trial_ends_at > now:
        sub_data["trial_end"] = int(account.trial_ends_at.timestamp())
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "client_reference_id": str(account.id),
        "subscription_data": sub_data,
        "success_url": f"{settings.web_base_url}/billing?checkout=success",
        "cancel_url": f"{settings.web_base_url}/billing?checkout=cancel",
    }
    # Reuse a known Stripe customer (avoids duplicates); else let Checkout mint
    # one from the email.
    existing = await _subscription_for_account(session, account.id)
    if existing is not None and existing.stripe_customer_id:
        params["customer"] = existing.stripe_customer_id
    else:
        params["customer_email"] = account.email
    checkout = await stripe.checkout.Session.create_async(**params)
    return checkout.url


async def create_portal_session(session: AsyncSession, account: Account) -> str:
    """A Stripe Customer Portal URL (manage/cancel). 402 if no Stripe customer."""
    _configure_stripe()
    sub = await _subscription_for_account(session, account.id)
    if sub is None or not sub.stripe_customer_id:
        raise BillingError("No active subscription to manage.")
    portal = await stripe.billing_portal.Session.create_async(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.web_base_url}/billing",
    )
    return portal.url


def verify_webhook(payload: bytes, signature: str | None) -> stripe.Event:
    """Verify a webhook's signature and parse it (raises on tamper/replay skew).

    Pure crypto over the raw body — no network — so it stays synchronous. A bad
    signature raises, which the router turns into a 400 (never process it).
    """
    return stripe.Webhook.construct_event(payload, signature or "", settings.stripe_webhook_secret)


# --- webhook state machine (the ONLY place entitlement changes) ----------
async def _subscription_for_account(session: AsyncSession, account_id: UUID) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.account_id == account_id))


async def _account_from_event_object(session: AsyncSession, obj: Any) -> Account | None:
    """Resolve the owning Account from a Stripe object.

    Prefer the `account_id` we stamped into subscription metadata (order-
    independent); fall back to a lookup by `stripe_customer_id` (e.g. invoices,
    which carry no metadata).
    """
    metadata = obj.get("metadata") or {}
    account_id = metadata.get("account_id")
    if account_id:
        # Metadata is attacker-influenceable in theory; a malformed id must not
        # 500 the webhook (Stripe would then retry it forever). Treat an
        # unparseable id as "unattributable" and fall through to the customer.
        try:
            return await session.get(Account, UUID(account_id))
        except ValueError:
            logger.warning("webhook carried a malformed account_id metadata value")
    customer = obj.get("customer")
    if customer:
        sub = await session.scalar(
            select(Subscription).where(Subscription.stripe_customer_id == customer)
        )
        if sub is not None:
            return await session.get(Account, sub.account_id)
    return None


def _to_dt(unix: int | None) -> datetime | None:
    return datetime.fromtimestamp(unix, tz=UTC) if unix else None


async def _upsert_subscription(session: AsyncSession, account: Account, obj: Any) -> None:
    """Apply a Stripe subscription object to account entitlement + the mirror row."""
    item = obj["items"]["data"][0]
    price_id = item["price"]["id"]
    tier = _tier_for_price(price_id)
    status = obj["status"]  # active | trialing | past_due | canceled | ...

    account.plan = tier
    account.status = status

    sub = await _subscription_for_account(session, account.id)
    if sub is None:
        sub = Subscription(account_id=account.id)
        session.add(sub)
    sub.stripe_customer_id = obj.get("customer")
    sub.stripe_subscription_id = obj.get("id")
    sub.stripe_price_id = price_id
    sub.status = status
    sub.plan = tier
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    # `current_period_end` moved from the subscription object onto the
    # subscription item in Stripe API 2025-03-31.basil+. Read the item first,
    # falling back to the legacy top-level field for older API versions.
    sub.current_period_end = _to_dt(item.get("current_period_end") or obj.get("current_period_end"))


async def _handle_subscription_deleted(session: AsyncSession, account: Account, obj: Any) -> None:
    account.plan = FREE_PLAN
    account.status = "canceled"
    sub = await _subscription_for_account(session, account.id)
    if sub is not None:
        sub.status = "canceled"
        sub.cancel_at_period_end = False


async def _handle_payment_failed(session: AsyncSession, account: Account, obj: Any) -> None:
    # Keep serving (soft) and nudge — never yank access/data mid-cycle (§10).
    account.status = "past_due"
    sub = await _subscription_for_account(session, account.id)
    if sub is not None:
        sub.status = "past_due"


async def _render_trial_ending(account: Account) -> tuple[str, str]:
    subject = "Your Flowly trial is ending soon"
    text = (
        f"Hi {account.username},\n\n"
        "Your 7-day Flowly trial is ending soon. To keep your analytics running "
        f"without interruption, add a plan here: {settings.web_base_url}/billing\n"
    )
    return subject, text


async def on_event_committed(session: AsyncSession, event: Any) -> None:
    """Best-effort side effects to run AFTER the webhook transaction commits.

    Kept separate from `apply_subscription_event` (the state machine) so nothing
    here can affect entitlement or roll back on an email failure. Today: the
    `trial_will_end` nudge, sent as transactional mail (not opt-out-gated — it's
    billing-critical, and it never fails the webhook)."""
    if event["type"] != "customer.subscription.trial_will_end":
        return
    account = await _account_from_event_object(session, event["data"]["object"])
    if account is None:
        return
    subject, text = await _render_trial_ending(account)
    try:
        await send_email(account.email, subject, text)
    except Exception:
        logger.exception("trial_will_end email failed for account %s", account.id)


async def apply_subscription_event(session: AsyncSession, event: Any) -> None:
    """The webhook state machine — the single writer of account entitlement.

    Idempotency (dedupe by event id) is enforced by the caller in the same
    transaction; this function just applies the effect. Unknown event types and
    events we can't attribute to an account are no-ops.
    """
    etype = event["type"]
    obj = event["data"]["object"]
    account = await _account_from_event_object(session, obj)
    if account is None:
        return
    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        await _upsert_subscription(session, account, obj)
    elif etype == "customer.subscription.deleted":
        await _handle_subscription_deleted(session, account, obj)
    elif etype == "invoice.payment_failed":
        await _handle_payment_failed(session, account, obj)
    # customer.subscription.trial_will_end -> nudge (email) only; no state change.
    # checkout.session.completed -> the customer link is carried by subscription
    # metadata, so the subscription.created/updated event is authoritative.
