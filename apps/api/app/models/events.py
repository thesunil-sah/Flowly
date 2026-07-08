"""Ingestion request schema — the `/collect` wire contract (CLAUDE.md §4).

This mirrors the payload the Phase 2 tracker sends verbatim: `site_id`, `path`
(no query string), `referrer`, `screen_w`, and the three UTM fields. The tracker
posts a `text/plain` JSON body, so the router parses the raw body and validates
it here at the boundary.

`extra="ignore"` keeps ingestion forgiving: a stray field (e.g. a future or
dropped `language`) is dropped, not rejected. Enrichment fields the server
derives (visitor_hash, geo, device, ts, source, event_id) are NOT part of this
model — they are added downstream in the ingest service.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ClickHouse `screen_w` is a UInt16 — clamp to its range so a nonsense width
# never overflows the insert (and never rejects an otherwise-valid pageview).
_SCREEN_W_MAX = 65535


class CollectEvent(BaseModel):
    # Ignore unknown keys so the tracker can evolve without breaking ingestion.
    model_config = ConfigDict(extra="ignore")

    site_id: str = Field(min_length=1, max_length=64)
    # "pageview" (the default — every existing snippet) or "custom" (Phase 15
    # `flowly('event', name)`). An unknown/missing value coerces to "pageview" so
    # ingestion stays forgiving; a custom event carries a `name`.
    event_type: Literal["pageview", "custom"] = "pageview"
    # The custom-event name (e.g. "signup", "purchase"). Ignored for pageviews;
    # for a custom event with no usable name we fall back to "pageview" below.
    name: str | None = Field(default=None, max_length=64)
    path: str = Field(min_length=1, max_length=2048)
    # document.referrer may be "" — keep it optional-but-present.
    referrer: str = Field(default="", max_length=2048)
    screen_w: int = 0
    utm_source: str | None = Field(default=None, max_length=255)
    utm_medium: str | None = Field(default=None, max_length=255)
    utm_campaign: str | None = Field(default=None, max_length=255)
    # navigator.language from the tracker (Phase 11), e.g. "en-US". Optional so
    # older snippets that don't send it still validate.
    language: str | None = Field(default=None, max_length=35)

    @field_validator("event_type", mode="before")
    @classmethod
    def _default_event_type(cls, v: object) -> str:
        # Forgiving: an unknown/blank type coerces to "pageview" rather than
        # rejecting the whole event (§9 ingestion stays lenient).
        return v if v in ("pageview", "custom") else "pageview"

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, v: str | None) -> str | None:
        # Custom-event names are user-defined identifiers — keep their case but
        # trim; empty → None.
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("screen_w")
    @classmethod
    def _clamp_screen_w(cls, v: int) -> int:
        # Clamp rather than reject: a weird width shouldn't drop the pageview.
        return max(0, min(v, _SCREEN_W_MAX))

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, v: str | None) -> str | None:
        # Normalize a BCP-47 tag to lowercase (e.g. "en-US" → "en-us") so the
        # breakdown doesn't split on case. Keep the full tag; empty → None.
        if v is None:
            return None
        v = v.strip().lower()
        return v or None
