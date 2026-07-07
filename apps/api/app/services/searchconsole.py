"""Search Console — connection lifecycle, daily sync, and the SEO reports (§3).

The GSC HTTP calls live in `services/gscapi.py`; this module is the DB + business
layer. Three concerns:

  1. **Connect** — an authed user links a Flowly site to one of their verified GSC
     properties. A Redis-stored `state` binds the OAuth round-trip to `(account,
     site)` (the bearer token can't ride Google's top-level redirect), and the
     property is auto-matched to the site's domain. The refresh token is stored
     and **never logged or returned** (§9).
  2. **Sync** — `sync_site` re-pulls the trailing `GSC_SYNC_DAYS` days and, per
     day, deletes then re-inserts that day's rows — idempotent per (site, date),
     so a re-run (or a late GSC revision) self-heals.
  3. **Reports** — keyword / page performance + opportunity keywords, aggregated
     over a date range, impression-weighting the average position.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ValidationError
from app.models.tables import SearchConsoleConnection, SearchMetric, Site
from app.services import gscapi

logger = logging.getLogger("flowly.searchconsole")

_STATE_TTL = 600  # seconds — the user has 10 min to finish Google consent
# GSC finalizes data ~2 days late; don't sync the freshest (incomplete) days.
_GSC_LAG_DAYS = 2
# Manual "Sync now" pulls only the freshest days so the request stays snappy
# (the daily worker still re-pulls the full `gsc_sync_days` window in the
# background). One HTTP round-trip per day, so keep this small.
MANUAL_SYNC_DAYS = 3
# Opportunity band: "just off page one" — high impressions, mid position.
_OPP_MIN_POSITION = 5.0
_OPP_MAX_POSITION = 20.0
# Column widths (mirror `models/tables.py::SearchMetric`); GSC can return a page
# URL longer than the column, which would abort the whole day's insert on
# Postgres — truncate defensively so one long URL can't zero out a site's sync.
_QUERY_MAXLEN = 512
_PAGE_MAXLEN = 2048


# --- Connect state (Redis) ------------------------------------------------
async def create_connect_state(redis: object, account_id: UUID, site_id: str) -> str:
    """Mint a CSRF state binding this connect round-trip to (account, site)."""
    import secrets

    state = secrets.token_urlsafe(24)
    await redis.set(f"gsc:state:{state}", f"{account_id}:{site_id}", ex=_STATE_TTL)  # type: ignore[attr-defined]
    return state


async def consume_connect_state(redis: object, state: str) -> tuple[UUID, str]:
    """Resolve + delete a connect state → (account_id, public site_id)."""
    key = f"gsc:state:{state}"
    stored = await redis.get(key)  # type: ignore[attr-defined]
    if not stored:
        raise ValidationError("Invalid or expired connect state.")
    await redis.delete(key)  # type: ignore[attr-defined]
    account_str, _, site_id = stored.partition(":")
    return UUID(account_str), site_id


# --- Connection lifecycle -------------------------------------------------
async def get_connection(session: AsyncSession, site: Site) -> SearchConsoleConnection | None:
    return await session.scalar(
        select(SearchConsoleConnection).where(SearchConsoleConnection.site_id == site.id)
    )


async def store_connection(
    session: AsyncSession, site: Site, property_url: str, refresh_token: str
) -> SearchConsoleConnection:
    """Upsert the site's GSC connection (one property per site)."""
    conn = await get_connection(session, site)
    if conn is None:
        conn = SearchConsoleConnection(
            site_id=site.id, property_url=property_url, refresh_token=refresh_token
        )
        session.add(conn)
    else:
        conn.property_url = property_url
        conn.refresh_token = refresh_token
        conn.connected_at = datetime.now(UTC)
    await session.commit()
    return conn


async def disconnect(session: AsyncSession, site: Site) -> None:
    """Remove the connection AND its synced metrics (a clean revoke)."""
    await session.execute(delete(SearchMetric).where(SearchMetric.site_id == site.id))
    await session.execute(
        delete(SearchConsoleConnection).where(SearchConsoleConnection.site_id == site.id)
    )
    await session.commit()


async def link_from_callback(
    session: AsyncSession, site: Site, code: str
) -> SearchConsoleConnection:
    """Finish the OAuth round-trip: code → refresh token → match property → store.

    Raises `GscError` if the site's domain isn't a verified property in the
    connecting Google account (so the user knows to verify it in GSC first).
    """
    refresh_token = await gscapi.exchange_code(code)
    access_token = await gscapi.refresh_access_token(refresh_token)
    properties = await gscapi.list_properties(access_token)
    property_url = gscapi.match_property(site.domain, properties)
    if property_url is None:
        raise gscapi.GscError(
            f"No verified Search Console property found for {site.domain}. "
            "Add and verify it in Google Search Console, then reconnect."
        )
    return await store_connection(session, site, property_url, refresh_token)


# --- Sync -----------------------------------------------------------------
def _sync_window(now: datetime, days: int) -> list[date]:
    """The trailing `days` to (re)sync — freshest `_GSC_LAG_DAYS` skipped."""
    end = now.date() - timedelta(days=_GSC_LAG_DAYS)
    return [end - timedelta(days=offset) for offset in range(days)]


async def sync_site(
    session: AsyncSession,
    conn: SearchConsoleConnection,
    now: datetime | None = None,
    days: int | None = None,
) -> int:
    """Re-pull the trailing window for one connection. Returns rows written.

    `days` defaults to the full `gsc_sync_days` window (the daily worker); the
    manual "Sync now" endpoint passes a small `MANUAL_SYNC_DAYS` so the request
    doesn't block on ~30 sequential GSC round-trips. Idempotent per (site, date):
    each day is deleted then re-inserted, so a re-run replaces cleanly. The
    access token is minted once for the whole run.
    """
    now = now or datetime.now(UTC)
    days = days if days is not None else settings.gsc_sync_days
    access_token = await gscapi.refresh_access_token(conn.refresh_token)
    written = 0
    for day in _sync_window(now, days):
        rows = await gscapi.query_search_analytics(
            access_token, conn.property_url, day, settings.gsc_row_limit
        )
        await session.execute(
            delete(SearchMetric).where(
                SearchMetric.site_id == conn.site_id, SearchMetric.date == day
            )
        )
        session.add_all(
            SearchMetric(
                site_id=conn.site_id,
                date=day,
                query=r.query[:_QUERY_MAXLEN],
                page=r.page[:_PAGE_MAXLEN],
                clicks=r.clicks,
                impressions=r.impressions,
                position=r.position,
            )
            for r in rows
        )
        written += len(rows)
    conn.last_synced_at = now
    await session.commit()
    return written


async def sync_all(session: AsyncSession, now: datetime | None = None) -> int:
    """Sync every connected site once. Returns connections synced.

    Best-effort per site: one site's failure (expired token, GSC hiccup) is
    logged and never aborts the sweep. Tokens are never logged (§9).
    """
    now = now or datetime.now(UTC)
    # Iterate by id + re-fetch fresh each loop: a rollback in one iteration
    # expires the whole identity map, so holding the ORM rows across the loop
    # would lazy-load (sync IO) on the next access. Ids are plain UUIDs.
    conn_ids = (await session.scalars(select(SearchConsoleConnection.id))).all()
    synced = 0
    for conn_id in conn_ids:
        conn = await session.get(SearchConsoleConnection, conn_id)
        if conn is None:  # pragma: no cover - deleted mid-run
            continue
        site_id = conn.site_id  # capture before any failure expires it
        try:
            written = await sync_site(session, conn, now)
        except Exception:
            await session.rollback()
            logger.exception("GSC sync failed for site_id=%s", site_id)
            continue
        logger.info("GSC sync: site_id=%s wrote %s rows", site_id, written)
        synced += 1
    logger.info("GSC sync run complete; %s connections synced", synced)
    return synced


# --- Reports --------------------------------------------------------------
def _weighted_position() -> object:
    """Impression-weighted average position (lower = better), div-zero-guarded."""
    return func.sum(SearchMetric.position * SearchMetric.impressions) / func.nullif(
        func.sum(SearchMetric.impressions), 0
    )


def _aggregate(group_col: object, site_id: UUID, dfrom: date, dto: date) -> Select:
    """Base grouped aggregate over a date range (rows shaped by the caller)."""
    return (
        select(
            group_col.label("label"),
            func.sum(SearchMetric.clicks).label("clicks"),
            func.sum(SearchMetric.impressions).label("impressions"),
            _weighted_position().label("position"),
        )
        .where(
            SearchMetric.site_id == site_id,
            SearchMetric.date >= dfrom,
            SearchMetric.date <= dto,
        )
        .group_by(group_col)
    )


def _shape(rows: Sequence[object]) -> list[dict[str, object]]:
    """DB rows → serializable dicts with derived CTR + rounded position."""
    out: list[dict[str, object]] = []
    for r in rows:
        clicks = int(r.clicks or 0)  # type: ignore[attr-defined]
        impressions = int(r.impressions or 0)  # type: ignore[attr-defined]
        position = float(r.position or 0.0)  # type: ignore[attr-defined]
        out.append(
            {
                "label": str(r.label),  # type: ignore[attr-defined]
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "position": round(position, 1),
            }
        )
    return out


async def keyword_report(
    session: AsyncSession, site_id: UUID, dfrom: date, dto: date, limit: int
) -> list[dict[str, object]]:
    """Top search queries by clicks (then impressions)."""
    stmt = (
        _aggregate(SearchMetric.query, site_id, dfrom, dto)
        .order_by(func.sum(SearchMetric.clicks).desc(), func.sum(SearchMetric.impressions).desc())
        .limit(limit)
    )
    return _shape((await session.execute(stmt)).all())


async def page_report(
    session: AsyncSession, site_id: UUID, dfrom: date, dto: date, limit: int
) -> list[dict[str, object]]:
    """Pages ranked by search clicks."""
    stmt = (
        _aggregate(SearchMetric.page, site_id, dfrom, dto)
        .order_by(func.sum(SearchMetric.clicks).desc(), func.sum(SearchMetric.impressions).desc())
        .limit(limit)
    )
    return _shape((await session.execute(stmt)).all())


async def opportunity_report(
    session: AsyncSession, site_id: UUID, dfrom: date, dto: date, limit: int
) -> list[dict[str, object]]:
    """Queries at position ~5–20 with the most impressions — "just off page one".

    High impressions + a page-two-ish rank = the biggest, cheapest wins. Ranked
    by impressions (opportunity size), not clicks (which are low by definition).
    """
    pos = _weighted_position()
    stmt = (
        _aggregate(SearchMetric.query, site_id, dfrom, dto)
        .having(and_(pos >= _OPP_MIN_POSITION, pos <= _OPP_MAX_POSITION))
        .having(func.sum(SearchMetric.impressions) > 0)
        .order_by(func.sum(SearchMetric.impressions).desc())
        .limit(limit)
    )
    return _shape((await session.execute(stmt)).all())
