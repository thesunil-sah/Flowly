"""Site ownership + lookup — the tenant-isolation boundary (CLAUDE.md §9).

Every authed surface that serves site-scoped data (live traffic, historical
stats) must confirm the site belongs to the calling account *before* querying
by `site_id`. Filtering by `site_id` alone is the #1 way to leak one customer's
data to another; the `account_id` predicate here is what enforces ownership.

This module is the single home for that check so live/stats/onboarding share
one canonical query rather than each re-deriving it.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Site


async def get_owned_site(session: AsyncSession, site_id: str, account_id: UUID) -> Site | None:
    """Return the site iff it exists AND belongs to this account (tenant scope).

    Filtering by site_id alone is not enough (CLAUDE.md §9 — the #1 data-leak
    path); the account_id predicate is what enforces ownership.
    """
    return await session.scalar(
        select(Site).where(Site.site_id == site_id, Site.account_id == account_id)
    )


async def list_account_sites(session: AsyncSession, account_id: UUID) -> Sequence[Site]:
    """All of an account's sites, oldest first (ownership-scoped)."""
    result = await session.scalars(
        select(Site).where(Site.account_id == account_id).order_by(Site.created_at)
    )
    return result.all()
