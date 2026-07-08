"""GET/POST/DELETE /goals + GET /events — custom events & conversion goals.

Phase 15, the first premium feature. Every route is authed, **ownership-scoped**
(the site must belong to the caller — §9), and **entitlement-gated**: a free
account gets a 402 `UpgradeRequiredError` (`billing.require_premium`). Ingestion
still stores custom events for everyone (§9 never gates /collect); only reading
them is paid.

Handlers stay thin (§3): resolve+own the site, gate entitlement, call
`services/goals.py` (Postgres) or `services/stats.py` (ClickHouse), return the
model.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser
from app.core.statsfilters import FilterDep
from app.core.timerange import stats_range
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.models.schemas import EventsOut, GoalConversionOut, GoalIn, GoalOut
from app.models.tables import Site
from app.services import goals as goals_svc
from app.services import sites as sites_svc
from app.services import billing, stats

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RangeDep = Annotated[tuple[datetime, datetime], Depends(stats_range)]
LimitDep = Annotated[int, Query(ge=1, le=100)]

router = APIRouter(tags=["goals"])


async def owned_site(
    site_id: Annotated[str, Query(min_length=1)],
    account: CurrentUser,
    session: SessionDep,
) -> Site:
    """The caller's site, or 404 (never reveal another account's site exists, §9).
    Also enforces entitlement: custom-event reports are a paid feature."""
    # Gate first: a free account can't read this surface at all (Phase 15).
    billing.require_premium(account, datetime.now(UTC))
    site = await sites_svc.get_owned_site(session, site_id, account.id)
    if site is None:
        raise NotFoundError("Site not found.")
    return site


OwnedSite = Annotated[Site, Depends(owned_site)]


@router.get("/events")
async def get_events(
    site: OwnedSite,
    date_range: RangeDep,
    filters: FilterDep,
    client: ClickHouseDep,
    limit: LimitDep = 20,
) -> EventsOut:
    """Top custom events by volume over the range."""
    return await stats.events(client, site.site_id, *date_range, limit, filters)


@router.get("/goals")
async def list_goals(site: OwnedSite, session: SessionDep) -> list[GoalOut]:
    rows = await goals_svc.list_goals(session, site.id)
    return [goals_svc.to_goal_out(g) for g in rows]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(site: OwnedSite, data: GoalIn, session: SessionDep) -> GoalOut:
    goal = await goals_svc.create_goal(session, site.id, data.name, data.kind, data.target)
    return goals_svc.to_goal_out(goal)


@router.get("/goals/{goal_id}/conversions")
async def goal_conversions(
    goal_id: UUID,
    site: OwnedSite,
    date_range: RangeDep,
    filters: FilterDep,
    session: SessionDep,
    client: ClickHouseDep,
) -> GoalConversionOut:
    """One goal's conversion rate over the range (converting visitors ÷ visitors)."""
    goal = await goals_svc.get_owned_goal(session, goal_id, site.id)
    if goal is None:
        raise NotFoundError("Goal not found.")
    conversions, visitors, rate = await stats.goal_conversions(
        client, site.site_id, *date_range, goal.kind, goal.target, filters
    )
    return GoalConversionOut(
        goal=goals_svc.to_goal_out(goal),
        conversions=conversions,
        visitors=visitors,
        conversion_rate=rate,
    )


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: UUID, site: OwnedSite, session: SessionDep) -> None:
    goal = await goals_svc.get_owned_goal(session, goal_id, site.id)
    if goal is None:
        raise NotFoundError("Goal not found.")
    await goals_svc.delete_goal(session, goal)
