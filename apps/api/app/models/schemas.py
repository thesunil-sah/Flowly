"""Pydantic request/response schemas — validation at the boundary (CLAUDE.md §4).

Emails and usernames are normalized (lowercase + trimmed) by shared validators
so every entry point stores and looks up the same form.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

if TYPE_CHECKING:
    from app.models.tables import Account, Identity

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


# --- Contact (Phase F6) ---------------------------------------------------
class ContactRequest(BaseModel):
    """Public contact-form submission. `company` is a honeypot — a field hidden
    from real users; a non-empty value marks a bot and the message is dropped."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    message: str = Field(min_length=1, max_length=5000)
    company: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


# --- Account settings (Phase F3) ------------------------------------------
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = _Password


class ChangeEmailRequest(BaseModel):
    """Step 1 of an email change: confirm identity, target the new address.

    `password` re-authenticates the change; it is unused (and may be omitted)
    for OAuth-only accounts that have no password_hash.
    """

    new_email: EmailStr
    password: str | None = Field(default=None, max_length=128)

    @field_validator("new_email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class VerifyEmailChangeRequest(BaseModel):
    """Step 2: prove control of the new address with the emailed code."""

    new_email: EmailStr
    code: str = _Code

    @field_validator("new_email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class EmailPreferencesRequest(BaseModel):
    email_opt_out: bool


# --- Assistant / support chatbot (Phase F7) -------------------------------
class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AssistantReply(BaseModel):
    reply: str
    # Where the answer came from: a matched FAQ intent, the AI fallback, or the
    # canned contact fallback (unmatched + no AI available).
    source: Literal["faq", "ai", "fallback"]


class DeleteAccountRequest(BaseModel):
    """Password re-auth for the irreversible delete; optional for OAuth-only."""

    password: str | None = Field(default=None, max_length=128)


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
    """Public account shape — never exposes password_hash.

    `has_password` (derived, not a column) lets the settings UI decide whether to
    offer the change-password form; OAuth-only accounts have no password to change.
    Built via `from_account` so that derived field is always populated.
    """

    id: UUID
    username: str
    email: EmailStr
    plan: str
    status: str
    email_verified_at: datetime | None
    trial_ends_at: datetime | None
    email_opt_out: bool
    has_password: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_account(cls, account: "Account") -> "AccountOut":
        return cls(
            id=account.id,
            username=account.username,
            email=account.email,
            plan=account.plan,
            status=account.status,
            email_verified_at=account.email_verified_at,
            trial_ends_at=account.trial_ends_at,
            email_opt_out=account.email_opt_out,
            has_password=account.password_hash is not None,
        )


class IdentityOut(BaseModel):
    """A linked social login shown in settings (no provider_user_id exposed)."""

    id: UUID
    provider: str
    created_at: datetime

    @classmethod
    def from_identity(cls, identity: "Identity") -> "IdentityOut":
        return cls(id=identity.id, provider=identity.provider, created_at=identity.created_at)


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
    # Present only on the engagement ranking (sort="engagement"); None otherwise.
    avg_duration: int | None = None  # avg seconds on page
    bounce_rate: float | None = None  # percent of this page's views in 1-page sessions


class PagesOut(BaseModel):
    kind: str  # "top" | "entry" | "exit"
    metric: str  # what `count` means: "pageviews" | "sessions"
    rows: list[PageRow]


class ChannelRow(BaseModel):
    channel: str  # direct | search | social | ai | referral
    pageviews: int
    visitors: int


class ChannelsOut(BaseModel):
    channels: list[ChannelRow]


class HeatmapCell(BaseModel):
    dow: int  # 1=Monday … 7=Sunday (localized to the request timezone)
    hour: int  # 0–23 (localized)
    pageviews: int
    visitors: int


class HeatmapOut(BaseModel):
    timezone: str  # the IANA tz the cells were bucketed in
    cells: list[HeatmapCell]  # dense 7×24 grid (168 cells)


class UptimeIncidentOut(BaseModel):
    started_at: datetime
    resolved_at: datetime | None  # null while the incident is ongoing
    cause: str  # timeout | connect | dns | http_5xx | blocked
    ongoing: bool


class UptimeStatusOut(BaseModel):
    status: str  # up | down | unknown (never checked yet)
    last_checked_at: datetime | None
    last_status_code: int | None
    incidents: list[UptimeIncidentOut]  # most recent first


# --- Search Console (Phase 13) ---------------------------------------------
class GscAuthorizeOut(BaseModel):
    authorize_url: str  # Google consent URL; the browser navigates here


class GscConnectionOut(BaseModel):
    connected: bool
    property_url: str | None  # the linked GSC siteUrl; never the refresh token
    last_synced_at: datetime | None


class SearchRow(BaseModel):
    label: str  # the query (keyword/opportunity reports) or page URL
    clicks: int
    impressions: int
    ctr: float  # clicks / impressions (0..1)
    position: float  # impression-weighted average rank (lower = better)


class SearchReportOut(BaseModel):
    rows: list[SearchRow]


class GscSyncOut(BaseModel):
    rows_written: int
    last_synced_at: datetime | None
