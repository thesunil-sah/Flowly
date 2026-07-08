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

from app.config import FREE_MONTHLY_VIEWS, settings
from app.core.exceptions import AccountLockedError, BillingError, UpgradeRequiredError
from app.models.tables import Account, Subscription
from app.services.email import send_email

logger = logging.getLogger("flowly.billing")

# Two entitlement states under metered billing (Phase 14): `free` (no active
# subscription — the entry state and the fallback when a sub lapses/cancels) and
# `metered` (an active/trialing/past-due metered subscription).
FREE_PLAN = "free"
PAID_PLAN = "metered"

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

    NB: metering NEVER gates ingestion (Phase 14, §9). The paywall locks the
    *dashboard* on the read side (`ensure_not_locked`); `/collect` keeps counting
    and returning 202 even for a locked account, so its charts stay hole-free.
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
    """The entitlement state the account is actually in right now — `metered` or
    `free`.

    Entitlement is derived, never separately stored: an active or past-due
    subscription (past-due keeps serving — §10) is `metered`; an in-window trial
    is `metered`; anything else — a lapsed card-free trial or a canceled
    subscription — falls back to `free`. This is why a never-paid expired trial
    needs no webhook to "downgrade" it.
    """
    if account.status in ("active", "past_due"):
        return PAID_PLAN
    if account.status == "trialing" and (
        account.trial_ends_at is None or _as_utc(account.trial_ends_at) > now
    ):
        return PAID_PLAN
    return FREE_PLAN


def require_dimension_access(account: Account, dimension: str, now: datetime) -> None:
    """Raise `UpgradeRequiredError` if `dimension` is paid-only and the account's
    effective plan is free. A no-op for free dimensions or paying accounts.

    Called from every read path that serves audience breakdowns (authed stats,
    public share, CSV export) so the gate isn't UI-only (§9)."""
    if dimension in PAID_AUDIENCE_DIMENSIONS and effective_plan(account, now) == FREE_PLAN:
        raise UpgradeRequiredError()


def require_premium(account: Account, now: datetime) -> None:
    """Raise `UpgradeRequiredError` if the account is on the free plan (Phase 15).

    Gates the premium feature surface (custom-event reports + conversion goals):
    ingestion still stores custom events for everyone (§9 — never gate /collect),
    but only a paying (metered) account can *read* them. Enforced server-side on
    every goals/events route so the gate isn't UI-only (§9)."""
    if effective_plan(account, now) == FREE_PLAN:
        raise UpgradeRequiredError()


def is_locked(account: Account, used: int, now: datetime) -> bool:
    """True when a FREE account has passed the free monthly-view limit (Phase 14).

    A locked account's *dashboard* reads are gated (blocking paywall + 402);
    ingestion is never gated (§9). A paying (metered) account is never locked —
    it's billed for the overage, not walled off.
    """
    return effective_plan(account, now) == FREE_PLAN and used > FREE_MONTHLY_VIEWS


async def ensure_not_locked(redis: Redis, account: Account, now: datetime | None = None) -> None:
    """Raise `AccountLockedError` (402) if the account is locked (Phase 14).

    The server-side half of the paywall: every gated dashboard read (stats, live,
    public share, CSV export) calls this so the wall isn't UI-only (§9). Ingestion
    (`/collect`) NEVER calls it — a locked account keeps its charts hole-free.
    """
    now = now or datetime.now(UTC)
    used = await get_usage(redis, account.id, now)
    if is_locked(account, used, now):
        raise AccountLockedError()


def usage_status(plan: str, used: int) -> str:
    """`ok` | `warning` (≥80% of free) | `locked` (>free) — drives the UI.

    Only free accounts warn/lock; a metered account is always `ok` (its banner
    shows a running bill estimate instead, computed client-side from the same
    graduated schedule).
    """
    if plan != FREE_PLAN:
        return "ok"
    if used > FREE_MONTHLY_VIEWS:
        return "locked"
    if used >= FREE_MONTHLY_VIEWS * _WARNING_FRACTION:
        return "warning"
    return "ok"


async def usage_summary(
    redis: Redis, account: Account, now: datetime | None = None
) -> dict[str, object]:
    """The `/billing/usage` payload: plan, quota, used, pct, status.

    Read-time only — the hot path never computes this. `quota` is the free
    monthly allotment (what `pct` is measured against); `pct` is rounded so the
    UI never shows a float artifact (§4).
    """
    now = now or datetime.now(UTC)
    plan = effective_plan(account, now)
    used = await get_usage(redis, account.id, now)
    quota = FREE_MONTHLY_VIEWS
    pct = round(used / quota * 100, 1) if quota > 0 else 100.0
    return {
        "plan": plan,
        "quota": quota,
        "used": used,
        "pct": pct,
        "status": usage_status(plan, used),
    }


# --- Stripe (entitlement) -------------------------------------------------
# All entitlement (account.plan/status) is granted ONLY by the webhook handlers
# below, from a signature-verified event — never from a Checkout redirect (§10).

# The repositioned 7-day trial (Phase 14) — starts at upgrade, once per account.
TRIAL_DAYS = 7


def _configure_stripe() -> None:
    """Point the SDK at our secret key (cheap; idempotent per process)."""
    stripe.api_key = settings.stripe_secret_key


def _tier_for_price(price_id: str) -> str:
    """Reverse a Stripe price id to its entitlement state (unknown/empty → free)."""
    metered = settings.stripe_price_metered
    if metered and price_id == metered:
        return PAID_PLAN
    return FREE_PLAN


def _has_used_trial(account: Account) -> bool:
    """Whether this account has already consumed its one lifetime trial.

    Recorded by stamping `trial_ends_at` when a trial starts (the trialing
    webhook), so a re-subscribe after a canceled/expired trial gets no second
    one. The trial no longer starts at signup (Phase 14) — a brand-new account
    has `trial_ends_at is None`.
    """
    return account.trial_ends_at is not None


async def create_checkout_session(session: AsyncSession, account: Account) -> str:
    """A Stripe Checkout URL for `account` to start the metered subscription.

    `client_reference_id` + subscription metadata carry the account id so the
    webhook can attribute the resulting subscription regardless of event order.
    A first-time subscriber gets the 7-day trial (§10 — repositioned to upgrade);
    an account that already used its trial subscribes immediately (one per
    account). The metered line item carries no quantity — usage is metered to the
    Billing Meter, not set at Checkout.

    An account that already has an active/past-due subscription is sent to the
    Customer Portal instead — re-running Checkout would mint a *second* live
    Stripe subscription (double billing). Where we already know the account's
    Stripe customer, it's reused so Checkout can't create a duplicate customer.
    """
    _configure_stripe()
    if not settings.stripe_price_metered:
        raise BillingError("Billing is not configured on this server.")
    # Block Checkout for ANY already-entitled account — active, past-due, OR an
    # in-window trial. Guarding only active/past_due let a *trialing* user re-run
    # Checkout and mint a SECOND live subscription (double billing); a trial is
    # `metered` too, so gate on the derived entitlement, not a status subset.
    if effective_plan(account, datetime.now(UTC)) == PAID_PLAN:
        raise BillingError(
            "You already have an active subscription. Use the customer portal to change plans."
        )
    sub_data: dict[str, Any] = {"metadata": {"account_id": str(account.id)}}
    if not _has_used_trial(account):
        sub_data["trial_period_days"] = TRIAL_DAYS
    params: dict[str, Any] = {
        "mode": "subscription",
        # Metered price → no `quantity` (Stripe meters usage from meter events).
        "line_items": [{"price": settings.stripe_price_metered}],
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


# --- Usage push to Stripe (Redis truth → Stripe meter) -------------------
# Redis stays the real-time source of truth for usage; Stripe's Billing Meter is
# fed periodically (a worker) so it can bill the graduated tiers. Meter events
# are *additive* (Stripe sums them), so we push the DELTA since the last push.
#
# The "already reported" high-water mark lives in **Postgres** (on the
# Subscription mirror), NOT Redis: if it could be evicted independently of the
# ephemeral usage counter, the next run would re-push a whole month and Stripe
# would double-bill (§9). With a durable marker the worst case on a Redis flush
# is *under*-billing (counter resets < marker → delta ≤ 0 → skip), never over.
def _period(now: datetime) -> str:
    return f"{now:%Y%m}"


async def _push_meter_event(customer_id: str, value: int) -> None:
    """Send one additive usage delta to the Stripe Billing Meter."""
    await stripe.billing.MeterEvent.create_async(
        event_name=settings.stripe_meter_event,
        payload={"stripe_customer_id": customer_id, "value": str(value)},
    )


async def report_usage_to_stripe(
    session: AsyncSession, redis: Redis, now: datetime | None = None
) -> int:
    """Push each metered account's usage delta to Stripe. Returns accounts pushed.

    Best-effort per account: one failure (Stripe hiccup) is logged and never
    aborts the sweep. Only entitled (metered) accounts with a Stripe customer are
    pushed. The delta is `current_month_usage - already_reported`, where
    `already_reported` is the DURABLE Postgres high-water mark for this calendar
    month (reset on rollover). The marker is advanced only after a successful
    push, so a failed push retries the same delta next run rather than losing it.
    """
    now = now or datetime.now(UTC)
    if not settings.stripe_price_metered:
        return 0
    _configure_stripe()
    period = _period(now)
    subs = (await session.scalars(select(Subscription))).all()
    pushed = 0
    for sub in subs:
        if not sub.stripe_customer_id:
            continue
        account = await session.get(Account, sub.account_id)
        if account is None or effective_plan(account, now) != PAID_PLAN:
            continue
        current = await get_usage(redis, account.id, now)
        # A new calendar month starts the high-water mark fresh (Stripe's own
        # meter resets per billing period); within a month it's the stored value.
        reported = sub.metered_usage_reported if sub.metered_usage_period == period else 0
        delta = current - reported
        if delta <= 0:
            # Nothing new to bill. Still roll the marker into the new month so a
            # later push this month measures its delta from 0, not last month.
            if sub.metered_usage_period != period:
                sub.metered_usage_period = period
                sub.metered_usage_reported = current
            continue
        try:
            await _push_meter_event(sub.stripe_customer_id, delta)
        except Exception:
            logger.exception("usage push to Stripe failed for account %s", account.id)
            continue
        sub.metered_usage_reported = current
        sub.metered_usage_period = period
        pushed += 1
    await session.commit()
    logger.info("usage push complete; %s accounts reported", pushed)
    return pushed


def verify_webhook(payload: bytes, signature: str | None) -> stripe.Event:
    """Verify a webhook's signature and parse it (raises on tamper/replay skew).

    Pure crypto over the raw body — no network — so it stays synchronous. A bad
    signature raises, which the router turns into a 400 (never process it).
    """
    return stripe.Webhook.construct_event(payload, signature or "", settings.stripe_webhook_secret)


# --- webhook state machine (the ONLY place entitlement changes) ----------
async def _subscription_for_account(session: AsyncSession, account_id: UUID) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.account_id == account_id))


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a key from a Stripe event object OR a plain dict.

    Stripe's ``StripeObject`` (what ``construct_event`` yields on a REAL webhook)
    is not a dict subclass and has no ``.get()`` — calling ``obj.get(...)`` raises
    ``AttributeError`` and 500s the webhook (so a real subscription never lands).
    It does support ``in`` and ``[]``, which also work on the plain dicts the
    tests pass, so this one accessor bridges both without special-casing.
    """
    return obj[key] if key in obj else default


async def _account_from_event_object(session: AsyncSession, obj: Any) -> Account | None:
    """Resolve the owning Account from a Stripe object.

    Prefer the `account_id` we stamped into subscription metadata (order-
    independent); fall back to a lookup by `stripe_customer_id` (e.g. invoices,
    which carry no metadata).
    """
    metadata = _field(obj, "metadata") or {}
    account_id = _field(metadata, "account_id")
    if account_id:
        # Metadata is attacker-influenceable in theory; a malformed id must not
        # 500 the webhook (Stripe would then retry it forever). Treat an
        # unparseable id as "unattributable" and fall through to the customer.
        try:
            return await session.get(Account, UUID(account_id))
        except ValueError:
            logger.warning("webhook carried a malformed account_id metadata value")
    customer = _field(obj, "customer")
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

    # Stamp when a trial ends so the account can't get a second one (one trial
    # per account, Phase 14). `trial_end` is only present while/after a trial;
    # once set we never clear it, so a re-subscribe skips the trial.
    trial_end = _to_dt(_field(obj, "trial_end"))
    if trial_end is not None:
        account.trial_ends_at = trial_end

    sub = await _subscription_for_account(session, account.id)
    if sub is None:
        sub = Subscription(account_id=account.id)
        session.add(sub)
    sub.stripe_customer_id = _field(obj, "customer")
    sub.stripe_subscription_id = _field(obj, "id")
    sub.stripe_price_id = price_id
    sub.status = status
    sub.plan = tier
    sub.cancel_at_period_end = bool(_field(obj, "cancel_at_period_end"))
    # `current_period_end` moved from the subscription object onto the
    # subscription item in Stripe API 2025-03-31.basil+. Read the item first,
    # falling back to the legacy top-level field for older API versions.
    sub.current_period_end = _to_dt(_field(item, "current_period_end") or _field(obj, "current_period_end"))


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
