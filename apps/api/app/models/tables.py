"""ORM tables — the Postgres metadata layer (CLAUDE.md Core data model).

Ids are UUIDs generated app-side (non-enumerable, no DB extension needed).
All timestamps are timezone-aware UTC (CLAUDE.md §4).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
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
    # Tier vs state are separate: `plan` is the tier, `status` the lifecycle.
    plan: Mapped[str] = mapped_column(String(32), default="pro")
    status: Mapped[str] = mapped_column(String(32), default="trialing")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
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
    __table_args__ = (
        UniqueConstraint("account_id", "domain", name="uq_site_account_domain"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    # Baseline schema only — no billing logic touches this until Phase 7.
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), default=None)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), default=None)
    status: Mapped[str | None] = mapped_column(String(32), default=None)
    plan: Mapped[str | None] = mapped_column(String(32), default=None)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
