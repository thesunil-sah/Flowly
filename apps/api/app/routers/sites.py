"""Site onboarding — add a site, get its snippet, verify the install (§3).

The permanent home for the sites CRUD surface (Phase 6). `GET /sites` lived in
`routers/live.py` during Phase 4 as a borrow; it moves here.

Every per-site route is authed and **ownership-scoped**: the `owned_site`
dependency confirms the `site_id` (a *path* param here) belongs to the caller and
raises 404 before any Redis/ClickHouse work — filtering by `site_id` alone is the
#1 multi-tenant leak path (§9). Routers stay thin: parse, depend, call
`services/sites.py`, return the model.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import ShareLinkOut, SiteCreate, SiteOut, SiteStatus, UptimeStatusOut
from app.models.tables import Site
from app.services import sharing, sites, uptime

router = APIRouter(prefix="/sites", tags=["sites"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


async def owned_site(
    site_id: str,
    account: CurrentUser,
    session: SessionDep,
) -> Site:
    """Resolve a path `site_id` to the caller's own site; 404 if not theirs.

    Returns the ORM row so handlers don't re-query. 404 (never 403) so the API
    never reveals a site exists under another account (§9).
    """
    site = await sites.get_owned_site(session, site_id, account.id)
    if site is None:
        raise NotFoundError("Site not found.")
    return site


OwnedSite = Annotated[Site, Depends(owned_site)]


@router.get("")
async def list_sites(account: CurrentUser, session: SessionDep) -> list[SiteOut]:
    """The authenticated account's sites (ownership-scoped)."""
    owned = await sites.list_account_sites(session, account.id)
    return [sites.to_site_out(s) for s in owned]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_site(
    data: SiteCreate, account: CurrentUser, session: SessionDep, redis: RedisDep
) -> SiteOut:
    """Register a new site and return it with its install snippet."""
    site = await sites.create_site(session, redis, account.id, data.domain)
    return sites.to_site_out(site)


@router.get("/{site_id}")
async def get_site(site: OwnedSite) -> SiteOut:
    """A single owned site (for deep-linking to its install screen)."""
    return sites.to_site_out(site)


@router.get("/{site_id}/status")
async def get_site_status(site: OwnedSite, redis: RedisDep, client: ClickHouseDep) -> SiteStatus:
    """Install verification: has the site received its first event yet?"""
    connected = await sites.first_event_seen(redis, client, site.site_id)
    return SiteStatus(connected=connected)


@router.get("/{site_id}/uptime")
async def get_site_uptime(site: OwnedSite, session: SessionDep) -> UptimeStatusOut:
    """Current up/down status + recent incidents for the site (Phase 12)."""
    return await uptime.get_status(session, site)


@router.get("/{site_id}/share")
async def get_share_link(site: OwnedSite, session: SessionDep) -> ShareLinkOut:
    """The site's current public share link (null if none is active)."""
    share = await sharing.active_share(session, site)
    return ShareLinkOut(url=sharing.share_url(share.token) if share else None)


@router.post("/{site_id}/share", status_code=status.HTTP_201_CREATED)
async def create_share_link(site: OwnedSite, session: SessionDep) -> ShareLinkOut:
    """Create (or rotate) the site's public share link."""
    share = await sharing.create_share(session, site)
    return ShareLinkOut(url=sharing.share_url(share.token))


@router.delete("/{site_id}/share", status_code=status.HTTP_200_OK)
async def revoke_share_link(site: OwnedSite, session: SessionDep) -> ShareLinkOut:
    """Revoke the site's public share link (it stops resolving immediately)."""
    await sharing.revoke_shares(session, site)
    return ShareLinkOut(url=None)
