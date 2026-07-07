"""ORM tables — the Postgres metadata layer (CLAUDE.md Core data model).

Ids are UUIDs generated app-side (non-enumerable, no DB extension needed).
All timestamps are timezone-aware UTC (CLAUDE.md §4).
"""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Stored normalized (lowercase + trimmed) so the unique index is effectively
    # case-insensitive; login lookup and rate-limit keys use the same form.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Unique handle, stored lowercased; login accepts email OR username.
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Null for OAuth-only accounts (they authenticate via a linked identity).
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    # Null until the email is confirmed via a 6-digit code; login is blocked
    # while null.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Entitlement is derived from `status` (billing.effective_plan); `plan`
    # mirrors the current state ("free" | "metered") for display/debugging.
    # New accounts start free — the trial begins at upgrade, not signup (Phase 14).
    plan: Mapped[str] = mapped_column(String(32), default="free")
    status: Mapped[str] = mapped_column(String(32), default="free")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Opt-out flag for non-transactional email (weekly digest, onboarding
    # sequence). Toggled true by the signed unsubscribe link; transactional mail
    # (verify/reset) ignores it. Never null so the marketing-send gate is a clean
    # boolean check (Phase 8).
    email_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sites: Mapped[list["Site"]] = relationship(back_populates="account")
    identities: Mapped[list["Identity"]] = relationship(back_populates="account")


class Identity(Base):
    """A linked social login. One account may have several (google, github)."""

    __tablename__ = "identities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))  # "google" | "github"
    provider_user_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["Account"] = relationship(back_populates="identities")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_user"),
    )


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    # Public identifier shipped in the tracking snippet. NOT a secret, never
    # used for auth. Generation lives in the sites service (Phase 6).
    site_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["Account"] = relationship(back_populates="sites")

    # A domain is a per-account label; the same host under one account is a
    # duplicate. This constraint is the real arbiter behind create_site's
    # pre-check (which alone is not race-safe against concurrent adds).
    __table_args__ = (UniqueConstraint("account_id", "domain", name="uq_site_account_domain"),)


class ShareToken(Base):
    """A public, read-only share link for one site's dashboard (Phase 8).

    The token is an unguessable secret (unlike the public `site_id`) — anyone
    holding the link can view that site's stats, so it is treated like a bearer
    credential: minted with `secrets.token_urlsafe`, and revocable. Revocation is
    soft (`revoked_at`) so "rotate" = mint a new active row + stamp the old one;
    the public resolver only accepts rows with `revoked_at IS NULL`.
    """

    __tablename__ = "share_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # FK to the internal site pk (not the public site_id) so a deleted site takes
    # its share links with it; the resolver reads `site.site_id` for stats.
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    site: Mapped["Site"] = relationship()


class OnboardingEmail(Base):
    """Ledger of onboarding-sequence steps already sent to an account (Phase 8).

    One row per (account, step) is the idempotency key: the hourly worker only
    sends a step whose row is absent, then inserts it — so a re-run (or overlap)
    can never send the same step twice. Mirrors `ProcessedStripeEvent`.
    """

    __tablename__ = "onboarding_emails"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    step: Mapped[str] = mapped_column(String(32))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("account_id", "step", name="uq_onboarding_account_step"),)


class Subscription(Base):
    __tablename__ = "subscriptions"

    # The durable mirror of Stripe entitlement. Written ONLY by verified webhook
    # handlers (services/billing.py) — never from a Checkout redirect (§9/§10).
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), default=None)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), default=None)
    status: Mapped[str | None] = mapped_column(String(32), default=None)
    plan: Mapped[str | None] = mapped_column(String(32), default=None)
    # True once the customer cancels but keeps access until current_period_end;
    # drives the "cancels on {date}" UI. Non-null with a default so the column
    # is always a clean boolean.
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Durable high-water mark of usage already pushed to Stripe's Billing Meter,
    # for the calendar month `metered_usage_period` ("YYYYMM"). Lives in Postgres
    # (not Redis) so it can't be evicted independently of the ephemeral usage
    # counter — the delta-push would otherwise re-push a whole month and Stripe,
    # summing additive meter events, would DOUBLE-BILL (Phase 14 fix, §9).
    metered_usage_reported: Mapped[int] = mapped_column(Integer, default=0)
    metered_usage_period: Mapped[str | None] = mapped_column(String(6), default=None)


class UptimeMonitor(Base):
    """Current uptime state for one site — the pinger's cross-run memory (Phase 12).

    One row per site (created lazily on first check). `fail_streak` is what powers
    *retry-before-alarm*: an incident only opens once it crosses the configured
    threshold, so a single blip never pages the owner. `status` gives the
    dashboard a cheap read without scanning the incident ledger.
    """

    __tablename__ = "uptime_monitors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # 1:1 with a site; FK to the internal pk so a deleted site takes it along.
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), unique=True, index=True)
    # "up" | "down" | "unknown" (never checked yet).
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    # Consecutive failed *checks* (each check already does an in-run retry).
    fail_streak: Mapped[int] = mapped_column(Integer, default=0)
    # HTTP status of the last completed response, if any (null on a transport
    # failure — connect/DNS/timeout — where there was no response).
    last_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    site: Mapped["Site"] = relationship()


class UptimeIncident(Base):
    """A single down period for a site (Phase 12).

    The **open** incident (`resolved_at IS NULL`) is the alert-idempotency key:
    while it exists, further failed pings never re-alert — the down email fires
    once when it opens, the recovery email once when it resolves. Mirrors the
    "a row IS the guard" idiom of `OnboardingEmail` / `ProcessedStripeEvent`.
    """

    __tablename__ = "uptime_incidents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Why it went down: "timeout" | "connect" | "dns" | "http_5xx" | "blocked".
    cause: Mapped[str] = mapped_column(String(32), default="")
    # Whether the down / recovery email has been dispatched for this incident.
    # Best-effort: a failed send leaves the flag false so the next run retries.
    notified_down: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_up: Mapped[bool] = mapped_column(Boolean, default=False)

    site: Mapped["Site"] = relationship()


class SearchConsoleConnection(Base):
    """Links one Flowly site to a Google Search Console property (Phase 13).

    Holds the OAuth **refresh token** granting read-only access to that property's
    Search Analytics. The token is a live credential (§9): it is never logged and
    never returned in an API response — only the sync worker reads it, to mint a
    short-lived access token. (Encryption-at-rest is a recommended hardening; the
    column stores it plaintext today, guarded by never-log/never-return.)
    """

    __tablename__ = "search_console_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # 1:1 with a site; FK to the internal pk so a deleted site takes it along.
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), unique=True, index=True)
    # The GSC siteUrl, e.g. "sc-domain:example.com" or "https://example.com/".
    property_url: Mapped[str] = mapped_column(String(255))
    # Google OAuth refresh token — NEVER logged or returned (§9).
    refresh_token: Mapped[str] = mapped_column(String(512))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    site: Mapped["Site"] = relationship()


class SearchMetric(Base):
    """One day's Search Analytics row for a (query, page) on a site (Phase 13).

    Synced from GSC by `workers/searchconsole.py`, idempotent per (site, date):
    the sync deletes a day's rows then re-inserts, so a re-run replaces cleanly.
    CTR is derived (clicks/impressions) at read time — not stored.
    """

    __tablename__ = "search_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    query: Mapped[str] = mapped_column(String(512))
    page: Mapped[str] = mapped_column(String(2048))
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    # GSC's average result position for this row (1.0 = top). Lower is better.
    position: Mapped[float] = mapped_column(Float, default=0.0)


class ProcessedStripeEvent(Base):
    """Webhook idempotency ledger: one row per handled Stripe event id.

    The webhook handler inserts the event id in the SAME transaction that applies
    the event's effect, so a redelivered event (Stripe delivers at-least-once)
    is a primary-key collision → skipped. Exactly-once processing (§10).
    """

    __tablename__ = "processed_stripe_events"

    # Stripe's `evt_...` id is the natural primary key.
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
