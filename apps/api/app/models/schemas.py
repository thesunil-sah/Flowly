"""Pydantic request/response schemas — validation at the boundary (CLAUDE.md §4).

Emails and usernames are normalized (lowercase + trimmed) by shared validators
so every entry point stores and looks up the same form.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# Password floor 8; 128 cap keeps argon2 input bounded (hashing-DoS guard).
_Password = Field(min_length=8, max_length=128)
# 6-digit numeric code.
_Code = Field(pattern=r"^\d{6}$")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_username(value: str) -> str:
    return value.strip().lower()


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = _Password

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        return _normalize_username(v)


class LoginRequest(BaseModel):
    # Email or username.
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def _identifier(cls, v: str) -> str:
        return v.strip().lower()


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = _Code

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ResendCodeRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class VerifyResetRequest(BaseModel):
    email: EmailStr
    code: str = _Code

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str = _Password


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access-token lifetime in seconds


class MessageResponse(BaseModel):
    status: str
    # Populated only in local dev so the code can be surfaced without email.
    dev_code: str | None = None


class ResetTokenResponse(BaseModel):
    reset_token: str


class AccountOut(BaseModel):
    """Public account shape — never exposes password_hash."""

    id: UUID
    username: str
    email: EmailStr
    plan: str
    status: str
    email_verified_at: datetime | None
    trial_ends_at: datetime | None

    model_config = {"from_attributes": True}


class SiteOut(BaseModel):
    """Public site shape for the dashboard (site_id is public, not a secret).

    `snippet` is the ready-to-paste install tag; it is NOT an ORM column, so this
    model is always built via `services.sites.to_site_out` (never `model_validate`
    on the ORM row, which has no `snippet` attribute).
    """

    id: UUID
    site_id: str
    domain: str
    snippet: str


class SiteCreate(BaseModel):
    """Add-site request. `domain` is a cosmetic label, normalized to a bare host.

    The validator normalizes but never rejects (mirrors the never-raise host
    helper); an empty-after-normalize domain is rejected in `create_site`, so
    there is a single error path.
    """

    domain: str = Field(min_length=1, max_length=255)

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str) -> str:
        # Imported here to avoid a schemas -> services import at module load.
        from app.core.urls import normalize_host

        return normalize_host(v)


class SiteStatus(BaseModel):
    """Install-verification result: has the site received its first event yet?"""

    connected: bool


# --- Sharing (Phase 8) ----------------------------------------------------
class ShareLinkOut(BaseModel):
    """A site's public share link. `url` is null when no live link exists."""

    url: str | None = None


class PublicSiteOut(BaseModel):
    """Metadata for a public (shared) dashboard — no account info exposed.

    `show_badge` is true on the free tier (drives the "Powered by Flowly" badge,
    Phase 8); `domain` is the cosmetic site label.
    """

    domain: str
    show_badge: bool


# --- Billing (Phase 7) ----------------------------------------------------
class CheckoutRequest(BaseModel):
    """Start a subscription for a tier + billing interval."""

    tier: Literal["pro", "business"]
    interval: Literal["monthly", "annual"] = "monthly"


class CheckoutResponse(BaseModel):
    """A Stripe Checkout URL to redirect the browser to."""

    url: str


class PortalResponse(BaseModel):
    """A Stripe Customer Portal URL (manage / cancel)."""

    url: str


class UsageSummary(BaseModel):
    """Current-month usage vs the account's effective plan quota."""

    plan: str
    quota: int
    used: int
    pct: float
    status: str  # "ok" | "warning" (>=80%) | "over" (>=100%)


# --- Stats (Phase 5) ------------------------------------------------------
class MetricDelta(BaseModel):
    """One overview metric plus its prior-period comparison.

    `previous`/`change_pct` are null when no comparison was requested or the
    prior period was empty (a percentage against zero is undefined, not ∞).
    """

    value: float
    previous: float | None = None
    change_pct: float | None = None


class OverviewOut(BaseModel):
    pageviews: MetricDelta
    visitors: MetricDelta
    sessions: MetricDelta
    bounce_rate: MetricDelta  # percent
    avg_duration: MetricDelta  # seconds


class TimeseriesPoint(BaseModel):
    bucket: datetime  # UTC bucket start; localized at display
    pageviews: int
    visitors: int


class TimeseriesOut(BaseModel):
    interval: str  # "hour" | "day"
    points: list[TimeseriesPoint]


class BreakdownRow(BaseModel):
    label: str
    pageviews: int
    visitors: int


class BreakdownOut(BaseModel):
    dimension: str
    rows: list[BreakdownRow]


class UtmRow(BaseModel):
    utm_source: str
    utm_medium: str
    utm_campaign: str
    pageviews: int
    visitors: int


class SourcesOut(BaseModel):
    sources: list[BreakdownRow]
    utm: list[UtmRow]


class PageRow(BaseModel):
    label: str
    count: int  # pageviews for kind="top"; sessions for entry/exit
    visitors: int


class PagesOut(BaseModel):
    kind: str  # "top" | "entry" | "exit"
    metric: str  # what `count` means: "pageviews" | "sessions"
    rows: list[PageRow]
