"""Conversion goals — CRUD + ownership (Phase 15, first premium feature).

A goal is a per-site definition (a pageview path or a named custom event) whose
conversion rate is computed at read time from ClickHouse (`services/stats.py`).
This module owns only the Postgres definition rows and the tenant-isolation
boundary: every lookup is scoped through the owning site's `account_id` (§9), so
one account can never see or mutate another's goals.

Layering (§3): the router parses the request and gates entitlement; this service
holds the DB logic; `services/stats.py` runs the ClickHouse conversion query.
"""

import logging
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.schemas import GoalOut
from app.models.tables import Goal, Site

logger = logging.getLogger("flowly.goals")


def to_goal_out(goal: Goal) -> GoalOut:
    return GoalOut(id=goal.id, name=goal.name, kind=goal.kind, target=goal.target)


async def _owned_site_pk(session: AsyncSession, site_id: str, account_id: UUID) -> UUID | None:
    """The internal site pk iff the public `site_id` belongs to this account.

    Ownership is the account_id predicate, not the site_id alone (§9)."""
    return await session.scalar(
        select(Site.id).where(Site.site_id == site_id, Site.account_id == account_id)
    )


async def list_goals(session: AsyncSession, site_pk: UUID) -> Sequence[Goal]:
    """All goals for a site (already ownership-resolved to its pk), oldest first."""
    result = await session.scalars(
        select(Goal).where(Goal.site_id == site_pk).order_by(Goal.created_at)
    )
    return result.all()


async def create_goal(
    session: AsyncSession, site_pk: UUID, name: str, kind: str, target: str
) -> Goal:
    """Create a goal for a site. A duplicate (site, kind, target) → ConflictError.

    The UNIQUE constraint is the real arbiter (race-safe); the try/except turns a
    lost race into a clean 409 rather than a 500 (mirrors `sites.create_site`)."""
    goal = Goal(site_id=site_pk, name=name, kind=kind, target=target)
    session.add(goal)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A goal with this target already exists.") from exc
    await session.refresh(goal)
    return goal


async def get_owned_goal(session: AsyncSession, goal_id: UUID, site_pk: UUID) -> Goal | None:
    """A goal iff it exists AND belongs to the given (already owned) site."""
    return await session.scalar(select(Goal).where(Goal.id == goal_id, Goal.site_id == site_pk))


async def delete_goal(session: AsyncSession, goal: Goal) -> None:
    await session.delete(goal)
    await session.commit()
