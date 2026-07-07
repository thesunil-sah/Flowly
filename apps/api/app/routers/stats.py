"""GET /stats/... — historical dashboard metrics (CLAUDE.md §3).

Every endpoint is authed and **ownership-scoped**: the shared `owned_site`
dependency verifies the `site_id` belongs to the caller *before* any ClickHouse
query runs. Filtering ClickHouse by `site_id` alone is not ownership — it's the
#1 multi-tenant leak path (§9). Handlers stay thin: parse params, depend on
`owned_site` + `stats_range`, call `services/stats.py`, return the model.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser
from app.core.statsfilters import FilterDep
from app.core.timerange import stats_range
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import (
    BreakdownOut,
    ChannelsOut,
    HeatmapOut,
    OverviewOut,
    PagesOut,
    SourcesOut,
    TimeseriesOut,
)
from app.services import billing, export, sites, stats

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


async def require_unlocked(account: CurrentUser, redis: RedisDep) -> None:
    """Gate the whole dashboard read surface: a locked free account gets a 402
    (Phase 14 paywall). Server-side so the wall isn't UI-only (§9); ingestion is
    never gated."""
    await billing.ensure_not_locked(redis, account)


# Router-level dependency → every stats route (incl. CSV export) is lock-gated.
router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(require_unlocked)])


async def owned_site(
    site_id: Annotated[str, Query(min_length=1)],
    account: CurrentUser,
    session: SessionDep,
) -> str:
    """Verify the site belongs to the caller; 404 if not (never reveal existence)."""
    site = await sites.get_owned_site(session, site_id, account.id)
    if site is None:
        raise NotFoundError("Site not found.")
    return site.site_id


SiteDep = Annotated[str, Depends(owned_site)]
RangeDep = Annotated[tuple[datetime, datetime], Depends(stats_range)]
LimitDep = Annotated[int, Query(ge=1, le=100)]


@router.get("/overview")
async def get_overview(
    site_id: SiteDep,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    compare: Annotated[Literal["previous"] | None, Query()] = None,
) -> OverviewOut:
    # `compare=previous` opts into the prior equal-length period (plan D7).
    return await stats.overview(client, site_id, *date_range, compare == "previous", filters)


@router.get("/timeseries")
async def get_timeseries(
    site_id: SiteDep, date_range: RangeDep, filters: FilterDep, client: ClickHouseDep
) -> TimeseriesOut:
    return await stats.timeseries(client, site_id, *date_range, filters)


@router.get("/sources")
async def get_sources(
    site_id: SiteDep,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    limit: LimitDep = 10,
) -> SourcesOut:
    return await stats.sources(client, site_id, *date_range, limit, filters)


@router.get("/channels")
async def get_channels(
    site_id: SiteDep, date_range: RangeDep, filters: FilterDep, client: ClickHouseDep
) -> ChannelsOut:
    """The 5-way channel split (direct/search/social/ai/referral)."""
    return await stats.channels(client, site_id, *date_range, filters)


@router.get("/channels/{channel}")
async def get_channel_referrers(
    site_id: SiteDep,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    channel: Literal["search", "social", "ai"],
    limit: LimitDep = 10,
) -> BreakdownOut:
    """Referrer hosts within one channel (Search / Social / AI drill-down)."""
    return await stats.channel_referrers(client, site_id, *date_range, channel, limit, filters)


@router.get("/heatmap")
async def get_heatmap(
    site_id: SiteDep,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    tz: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
) -> HeatmapOut:
    """Pageviews per (day-of-week, hour), bucketed in the viewer's timezone (§4)."""
    return await stats.heatmap(client, site_id, *date_range, tz, filters)


@router.get("/audience")
async def get_audience(
    site_id: SiteDep,
    account: CurrentUser,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    dimension: Literal["country", "device", "browser", "os", "screen", "city", "language"],
    limit: LimitDep = 10,
) -> BreakdownOut:
    # City is a paid report — enforce server-side, not just in the UI (§9).
    billing.require_dimension_access(account, dimension, datetime.now(UTC))
    return await stats.audience(client, site_id, *date_range, dimension, limit, filters)


@router.get("/pages")
async def get_pages(
    site_id: SiteDep,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    kind: Literal["top", "entry", "exit"] = "top",
    sort: Literal["traffic", "engagement"] = "traffic",
    limit: LimitDep = 10,
) -> PagesOut:
    return await stats.pages(client, site_id, *date_range, kind, limit, filters, sort)


@router.get("/export")
async def get_export(
    site_id: SiteDep,
    account: CurrentUser,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    dataset: Literal[
        "overview", "timeseries", "sources", "audience", "pages", "channels", "screens", "heatmap"
    ] = "overview",
    dimension: Literal["country", "device", "browser", "os", "city", "language"] = "country",
    kind: Literal["top", "entry", "exit"] = "top",
    tz: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    limit: LimitDep = 100,
) -> Response:
    """Download an aggregated report as CSV (ownership-checked; no PII, §9)."""
    # Same paid-tier gate as the dashboard so export can't be a side door (§9).
    if dataset == "audience":
        billing.require_dimension_access(account, dimension, datetime.now(UTC))
    filename, content = await export.build_csv(
        client, site_id, *date_range, dataset, dimension, kind, limit, filters, tz
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
