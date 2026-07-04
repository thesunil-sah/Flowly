"""GET /stats/... — historical dashboard metrics (CLAUDE.md §3).

Every endpoint is authed and **ownership-scoped**: the shared `owned_site`
dependency verifies the `site_id` belongs to the caller *before* any ClickHouse
query runs. Filtering ClickHouse by `site_id` alone is not ownership — it's the
#1 multi-tenant leak path (§9). Handlers stay thin: parse params, depend on
`owned_site` + `stats_range`, call `services/stats.py`, return the model.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser
from app.core.timerange import stats_range
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.models.schemas import BreakdownOut, OverviewOut, PagesOut, SourcesOut, TimeseriesOut
from app.services import export, sites, stats

router = APIRouter(prefix="/stats", tags=["stats"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
    client: ClickHouseDep,
    compare: Annotated[Literal["previous"] | None, Query()] = None,
) -> OverviewOut:
    # `compare=previous` opts into the prior equal-length period (plan D7).
    return await stats.overview(client, site_id, *date_range, compare == "previous")


@router.get("/timeseries")
async def get_timeseries(
    site_id: SiteDep, date_range: RangeDep, client: ClickHouseDep
) -> TimeseriesOut:
    return await stats.timeseries(client, site_id, *date_range)


@router.get("/sources")
async def get_sources(
    site_id: SiteDep, date_range: RangeDep, client: ClickHouseDep, limit: LimitDep = 10
) -> SourcesOut:
    return await stats.sources(client, site_id, *date_range, limit)


@router.get("/audience")
async def get_audience(
    site_id: SiteDep,
    date_range: RangeDep,
    client: ClickHouseDep,
    dimension: Literal["country", "device", "browser", "os"],
    limit: LimitDep = 10,
) -> BreakdownOut:
    return await stats.audience(client, site_id, *date_range, dimension, limit)


@router.get("/pages")
async def get_pages(
    site_id: SiteDep,
    date_range: RangeDep,
    client: ClickHouseDep,
    kind: Literal["top", "entry", "exit"] = "top",
    limit: LimitDep = 10,
) -> PagesOut:
    return await stats.pages(client, site_id, *date_range, kind, limit)


@router.get("/export")
async def get_export(
    site_id: SiteDep,
    date_range: RangeDep,
    client: ClickHouseDep,
    dataset: Literal["overview", "timeseries", "sources", "audience", "pages"] = "overview",
    dimension: Literal["country", "device", "browser", "os"] = "country",
    kind: Literal["top", "entry", "exit"] = "top",
    limit: LimitDep = 100,
) -> Response:
    """Download an aggregated report as CSV (ownership-checked; no PII, §9)."""
    filename, content = await export.build_csv(
        client, site_id, *date_range, dataset, dimension, kind, limit
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
