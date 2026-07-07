"""Google Search Console HTTP layer — pure API calls, no DB (Phase 13).

Everything that talks to Google lives here so `services/searchconsole.py` stays
about connections + reports. Like the sign-in OAuth (`services/oauth.py`) this is
plain httpx — no google-api-python-client dependency. The webmasters.readonly
scope + offline access (for a refresh token) is the only difference from sign-in.

Tokens are credentials (§9): this module never logs them, and callers must never
return them to a client.
"""

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.core.exceptions import AppError

# Read-only Search Analytics access. Offline + consent so Google returns a
# refresh token we can store and re-use for the daily sync.
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SITES_URL = "https://searchconsole.googleapis.com/webmasters/v3/sites"
_HTTP_TIMEOUT = 20.0


class GscError(AppError):
    status_code = 400
    message = "Search Console request failed. Please try again."


@dataclass(frozen=True)
class GscRow:
    """One Search Analytics row for a (query, page) on a given day."""

    query: str
    page: str
    clicks: int
    impressions: int
    position: float


def callback_url() -> str:
    """The redirect Google returns to — register this in the OAuth client."""
    return f"{settings.api_base_url}/searchconsole/callback"


def build_authorize_url(state: str) -> str:
    """Google consent URL for the GSC connect flow (offline → refresh token)."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": GSC_SCOPE,
        "state": state,
        "access_type": "offline",
        # Force a refresh token even on re-consent (Google omits it otherwise).
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """Exchange an auth code for a **refresh token** (the durable credential)."""
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "redirect_uri": callback_url(),
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(_TOKEN_URL, data=data, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise GscError("Could not connect Search Console.")
    refresh = resp.json().get("refresh_token")
    if not refresh:
        # No refresh token (user already granted without prompt=consent, etc.).
        raise GscError("Google did not return offline access. Please try connecting again.")
    return refresh


async def refresh_access_token(refresh_token: str) -> str:
    """Mint a short-lived access token from a stored refresh token."""
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(_TOKEN_URL, data=data, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise GscError("Search Console access expired. Please reconnect.")
    token = resp.json().get("access_token")
    if not token:
        raise GscError("Search Console access expired. Please reconnect.")
    return token


async def list_properties(access_token: str) -> list[str]:
    """Verified GSC property siteUrls the user can read (excludes unverified)."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(_SITES_URL, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        raise GscError()
    entries = resp.json().get("siteEntry", [])
    return [
        e["siteUrl"]
        for e in entries
        if e.get("siteUrl") and e.get("permissionLevel") != "siteUnverifiedUser"
    ]


def match_property(domain: str, properties: list[str]) -> str | None:
    """Pick the GSC property that corresponds to `domain` (prefer sc-domain).

    GSC properties are either domain properties (`sc-domain:example.com`) or
    URL-prefix properties (`https://example.com/`). We try, in order:
    sc-domain, https, https+www, http, http+www — the first that the user
    actually has verified wins. Returns None if none match.
    """
    domain = domain.lower().removeprefix("www.")
    candidates = [
        f"sc-domain:{domain}",
        f"https://{domain}/",
        f"https://www.{domain}/",
        f"http://{domain}/",
        f"http://www.{domain}/",
    ]
    owned = {p.lower(): p for p in properties}
    for candidate in candidates:
        if candidate.lower() in owned:
            return owned[candidate.lower()]
    return None


async def query_search_analytics(
    access_token: str, property_url: str, day: date, row_limit: int
) -> list[GscRow]:
    """Pull one day's rows dimensioned by (query, page) for a property.

    GSC reports are date-scoped and lag ~2–3 days; the caller picks the day.
    `property_url` is path-encoded (a domain property contains a colon).
    """
    from urllib.parse import quote

    url = f"{_SITES_URL}/{quote(property_url, safe='')}/searchAnalytics/query"
    iso = day.isoformat()
    body = {
        "startDate": iso,
        "endDate": iso,
        "dimensions": ["query", "page"],
        "rowLimit": row_limit,
        "dataState": "all",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            url, json=body, headers={"Authorization": f"Bearer {access_token}"}
        )
    if resp.status_code != 200:
        raise GscError()
    rows: list[GscRow] = []
    for r in resp.json().get("rows", []):
        keys = r.get("keys", ["", ""])
        rows.append(
            GscRow(
                query=str(keys[0]) if len(keys) > 0 else "",
                page=str(keys[1]) if len(keys) > 1 else "",
                clicks=int(r.get("clicks", 0)),
                impressions=int(r.get("impressions", 0)),
                position=float(r.get("position", 0.0)),
            )
        )
    return rows
