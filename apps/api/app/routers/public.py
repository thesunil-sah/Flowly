"""Public shareable dashboard — unauthenticated, single-site, read-only (§8).

Access is by an unguessable share **token** (not the public `site_id`): the
`shared_site` dependency resolves a live token to exactly one Site and 404s
otherwise, so there is no way to widen to another site or reach account data.
Everything downstream reuses the Phase 5 stats services unchanged — this router
only swaps the auth model (token, not bearer) for the same read surface.

Served under the dashboard-locked CORS: the viewer loads the web app's
`/share/{token}` page (our own origin), which calls these routes. There is no
mutation here and no PII in stats output (§9).
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.timerange import RangeDep
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.models.schemas import (
    BreakdownOut,
    OverviewOut,
    PagesOut,
    PublicSiteOut,
    SourcesOut,
    TimeseriesOut,
)
from app.models.tables import Account, Site
from app.services import billing, sharing, stats

router = APIRouter(prefix="/public", tags=["public"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def shared_site(
    token: Annotated[str, Path(min_length=1)],
    session: SessionDep,
) -> Site:
    """Resolve a live share token to its Site; 404 on unknown/revoked (never
    reveal which). This is the only gate on the public read surface (§9)."""
    site = await sharing.resolve_share(session, token)
    if site is None:
        raise NotFoundError("Dashboard not found.")
    return site


SharedSite = Annotated[Site, Depends(shared_site)]
LimitDep = Annotated[int, Query(ge=1, le=100)]


@router.get("/{token}")
async def get_public_meta(site: SharedSite, session: SessionDep) -> PublicSiteOut:
    """Shared-dashboard metadata: the site label + whether to show the badge.

    `show_badge` is true for a free-tier owner (Phase 8). Only the owning
    account's *effective plan* is read — no account identity is exposed.
    """
    account = await session.get(Account, site.account_id)
    show_badge = account is None or billing.effective_plan(account, datetime.now(UTC)) == "free"
    return PublicSiteOut(domain=site.domain, show_badge=show_badge)


@router.get("/{token}/overview")
async def get_overview(
    site: SharedSite,
    date_range: RangeDep,
    client: ClickHouseDep,
    compare: Annotated[Literal["previous"] | None, Query()] = None,
) -> OverviewOut:
    return await stats.overview(client, site.site_id, *date_range, compare == "previous")


@router.get("/{token}/timeseries")
async def get_timeseries(
    site: SharedSite, date_range: RangeDep, client: ClickHouseDep
) -> TimeseriesOut:
    return await stats.timeseries(client, site.site_id, *date_range)


@router.get("/{token}/sources")
async def get_sources(
    site: SharedSite, date_range: RangeDep, client: ClickHouseDep, limit: LimitDep = 10
) -> SourcesOut:
    return await stats.sources(client, site.site_id, *date_range, limit)


@router.get("/{token}/audience")
async def get_audience(
    site: SharedSite,
    date_range: RangeDep,
    client: ClickHouseDep,
    dimension: Literal["country", "device", "browser", "os"],
    limit: LimitDep = 10,
) -> BreakdownOut:
    return await stats.audience(client, site.site_id, *date_range, dimension, limit)


@router.get("/{token}/pages")
async def get_pages(
    site: SharedSite,
    date_range: RangeDep,
    client: ClickHouseDep,
    kind: Literal["top", "entry", "exit"] = "top",
    limit: LimitDep = 10,
) -> PagesOut:
    return await stats.pages(client, site.site_id, *date_range, kind, limit)
