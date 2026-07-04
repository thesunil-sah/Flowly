"""Site ownership + lookup — the tenant-isolation boundary (CLAUDE.md §9).

Every authed surface that serves site-scoped data (live traffic, historical
stats) must confirm the site belongs to the calling account *before* querying
by `site_id`. Filtering by `site_id` alone is the #1 way to leak one customer's
data to another; the `account_id` predicate here is what enforces ownership.

This module is the single home for that check so live/stats/onboarding share
one canonical query rather than each re-deriving it.
"""

import logging
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from clickhouse_connect.driver import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.urls import normalize_host
from app.db.clickhouse import query_rows
from app.models.schemas import SiteOut
from app.models.tables import Site
from app.services import billing, live

logger = logging.getLogger("flowly.sites")

# site_id bytes -> 16 hex chars. Public, non-secret; hex keeps it URL/HTML/Redis
# safe (no -_/+) and well within the sites.site_id String(64) column.
_SITE_ID_BYTES = 8
# Bounded retry if a generated id collides with the UNIQUE index (astronomically
# rare at 2^64; the DB constraint is the real guarantee, this is belt-and-braces).
_SITE_ID_MAX_TRIES = 3


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


async def list_all_sites(session: AsyncSession) -> Sequence[Site]:
    """Every site across all accounts (for cross-account maintenance jobs).

    Not ownership-scoped by design — its only callers are background workers
    (e.g. retention) that operate over the whole dataset, never a request path.
    """
    result = await session.scalars(select(Site).order_by(Site.created_at))
    return result.all()


def _generate_site_id() -> str:
    """A fresh public site_id (16 hex chars). Not a secret, never used for auth."""
    return secrets.token_hex(_SITE_ID_BYTES)


def build_snippet(site_id: str) -> str:
    """The ready-to-paste install tag. The script URL is server-owned (config)."""
    return f'<script defer src="{settings.tracker_script_url}" data-site="{site_id}"></script>'


def to_site_out(site: Site) -> SiteOut:
    """The one canonical SiteOut constructor — attaches the computed snippet.

    Every path (list, create, detail) builds the response through here so the
    shape is identical; the snippet is not an ORM column, so `model_validate`
    would omit it.
    """
    return SiteOut(
        id=site.id, site_id=site.site_id, domain=site.domain, snippet=build_snippet(site.site_id)
    )


async def create_site(session: AsyncSession, redis: Redis, account_id: UUID, domain: str) -> Site:
    """Register a new site for an account: normalize domain, mint a site_id, store.

    `domain` is a cosmetic dashboard label (events are scoped by site_id, not
    origin). It's normalized to a bare host; an empty result is rejected. A
    duplicate domain **for the same account** is a ConflictError — two different
    accounts may track the same domain, so the check is account-scoped.

    On success the immutable `site:{site_id} -> account_id` map is written to
    Redis so the ingest hot path can meter usage without a Postgres lookup
    (Phase 7). The write is best-effort — if it's lost, that site simply isn't
    metered until re-saved (usage under-counts; it never blocks ingestion).
    """
    host = normalize_host(domain)
    if not host:
        raise ValidationError("Enter a valid domain.")

    existing = await session.scalar(
        select(Site).where(Site.account_id == account_id, Site.domain == host)
    )
    if existing is not None:
        raise ConflictError("You've already added this site.")

    for _ in range(_SITE_ID_MAX_TRIES):
        site_id = _generate_site_id()
        if await session.scalar(select(Site).where(Site.site_id == site_id)) is None:
            break
    else:  # pragma: no cover - 3 collisions at 2^64 is effectively impossible
        raise ConflictError("Could not allocate a site id; please retry.")

    site = Site(account_id=account_id, site_id=site_id, domain=host)
    session.add(site)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Lost the race with a concurrent add that passed the pre-check too; the
        # (account_id, domain) unique constraint is the real arbiter. Surface a
        # clean 409 instead of letting the IntegrityError bubble up as a 500.
        await session.rollback()
        raise ConflictError("You've already added this site.") from exc
    await session.refresh(site)

    # Warm the site->account map for the ingest hot path (Phase 7). Best-effort:
    # a Redis hiccup must not fail site creation; a lost write only means this
    # site's usage isn't metered until it's re-saved.
    try:
        await billing.cache_site_account(redis, site.site_id, account_id)
    except Exception:
        logger.debug("site->account cache write failed for %s", site.site_id, exc_info=True)

    return site


def build_first_event_query(site_id: str) -> tuple[str, dict[str, str]]:
    """Existence probe: does ClickHouse hold any event for this site? (§9-safe).

    Server-parameterized (`{site_id:String}`) — the site_id is bound, never
    string-formatted in. `LIMIT 1` on the `(site_id, ts)` primary key is cheap.
    """
    sql = "SELECT 1 FROM events WHERE site_id = {site_id:String} LIMIT 1"
    return sql, {"site_id": site_id}


async def first_event_seen(redis: Redis, ch_client: AsyncClient, site_id: str) -> bool:
    """Has this site ever received an event? Redis-first, ClickHouse-fallback.

    Redis presence (`active:{site_id}`) flips true within a second of the first
    pageview — the snappy onboarding signal — but decays after the live window.
    The ClickHouse existence probe is durable (survives that window) but lags the
    batch writer by a few seconds. Checking both makes the "connected" flip both
    instant and permanent.
    """
    now = datetime.now(UTC).timestamp()
    if await live.count_active(redis, site_id, now) > 0:
        return True
    sql, params = build_first_event_query(site_id)
    return len(await query_rows(ch_client, sql, params)) > 0
