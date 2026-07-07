"""Search Console endpoints — connect, sync, and the SEO reports (Phase 13).

Every per-site route is authed and **ownership-scoped** via `owned_site` (404
before any work, §9). The one exception is the public `GET /searchconsole/callback`
— Google redirects the browser there with no bearer token, so it trusts the
Redis-stored `state` that `POST /{site_id}/connect` bound to (account, site), then
re-checks ownership before storing anything. Refresh tokens are never returned.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.core.security import CurrentUser
from app.core.timerange import RangeDep
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import (
    GscAuthorizeOut,
    GscConnectionOut,
    GscSyncOut,
    SearchReportOut,
    SearchRow,
)
from app.models.tables import Site
from app.services import gscapi, searchconsole, sites

router = APIRouter(prefix="/searchconsole", tags=["searchconsole"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
LimitDep = Annotated[int, Query(ge=1, le=100)]


async def owned_site(site_id: str, account: CurrentUser, session: SessionDep) -> Site:
    """Resolve a path `site_id` to the caller's own site; 404 if not theirs."""
    site = await sites.get_owned_site(session, site_id, account.id)
    if site is None:
        raise NotFoundError("Site not found.")
    return site


OwnedSite = Annotated[Site, Depends(owned_site)]


def _report_out(rows: list[dict[str, object]]) -> SearchReportOut:
    return SearchReportOut(rows=[SearchRow(**r) for r in rows])  # type: ignore[arg-type]


def _connection_out(conn: object | None) -> GscConnectionOut:
    if conn is None:
        return GscConnectionOut(connected=False, property_url=None, last_synced_at=None)
    return GscConnectionOut(
        connected=True,
        property_url=conn.property_url,  # type: ignore[attr-defined]
        last_synced_at=conn.last_synced_at,  # type: ignore[attr-defined]
    )


# --- Connect flow ---------------------------------------------------------
@router.post("/{site_id}/connect")
async def connect(site: OwnedSite, account: CurrentUser, redis: RedisDep) -> GscAuthorizeOut:
    """Begin the GSC connect: return the Google consent URL to navigate to."""
    if not (settings.google_client_id and settings.google_client_secret):
        raise ValidationError("Search Console is not configured on this server.")
    state = await searchconsole.create_connect_state(redis, account.id, site.site_id)
    return GscAuthorizeOut(authorize_url=gscapi.build_authorize_url(state))


def _web_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.web_base_url}/search-console/keywords?{urlencode(params)}")


@router.get("/callback")
async def callback(
    session: SessionDep,
    redis: RedisDep,
    state: str,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Google's redirect back: link the property, then bounce to the web app."""
    try:
        if error or not code:
            raise ValidationError("Search Console connection was cancelled.")
        account_id, site_id = await searchconsole.consume_connect_state(redis, state)
        site = await sites.get_owned_site(session, site_id, account_id)
        if site is None:
            raise NotFoundError("Site not found.")
        await searchconsole.link_from_callback(session, site, code)
    except AppError as exc:
        return _web_redirect(gsc="error", message=exc.message)
    return _web_redirect(gsc="connected")


# --- Connection management ------------------------------------------------
@router.get("/{site_id}/connection")
async def get_connection(site: OwnedSite, session: SessionDep) -> GscConnectionOut:
    return _connection_out(await searchconsole.get_connection(session, site))


@router.delete("/{site_id}/connection")
async def delete_connection(site: OwnedSite, session: SessionDep) -> GscConnectionOut:
    await searchconsole.disconnect(session, site)
    return _connection_out(None)


@router.post("/{site_id}/sync")
async def sync(site: OwnedSite, session: SessionDep) -> GscSyncOut:
    """Pull the freshest days of Search Analytics now (a bounded window so the
    request stays fast); the daily worker still re-pulls the full window."""
    conn = await searchconsole.get_connection(session, site)
    if conn is None:
        raise ValidationError("Connect Search Console first.")
    written = await searchconsole.sync_site(
        session, conn, days=searchconsole.MANUAL_SYNC_DAYS
    )
    return GscSyncOut(rows_written=written, last_synced_at=conn.last_synced_at)


# --- Reports --------------------------------------------------------------
@router.get("/{site_id}/keywords")
async def keywords(
    site: OwnedSite, session: SessionDep, date_range: RangeDep, limit: LimitDep = 25
) -> SearchReportOut:
    rows = await searchconsole.keyword_report(
        session, site.id, date_range[0].date(), date_range[1].date(), limit
    )
    return _report_out(rows)


@router.get("/{site_id}/pages")
async def pages(
    site: OwnedSite, session: SessionDep, date_range: RangeDep, limit: LimitDep = 25
) -> SearchReportOut:
    rows = await searchconsole.page_report(
        session, site.id, date_range[0].date(), date_range[1].date(), limit
    )
    return _report_out(rows)


@router.get("/{site_id}/opportunities")
async def opportunities(
    site: OwnedSite, session: SessionDep, date_range: RangeDep, limit: LimitDep = 25
) -> SearchReportOut:
    rows = await searchconsole.opportunity_report(
        session, site.id, date_range[0].date(), date_range[1].date(), limit
    )
    return _report_out(rows)
