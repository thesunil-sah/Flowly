"""Per-plan data retention — the cutoff logic + delete builder (§9, Phase 9).

Flowly promises per-plan retention (free 30d / pro 1y / business 2y — `config.
RETENTION_DAYS`). The retention worker deletes ClickHouse events older than each
site owner's window. The window is derived from the owner's **effective plan**
(a lapsed trial is `free`, so its data ages out at 30 days), never a stored flag.

Following §3, the SQL text lives here as a pure `(sql, params)` builder; the
site_id and cutoff are bound server-side (never string-formatted, §9). The delete
is scoped by `site_id` so one account's retention can never touch another's data.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from clickhouse_connect.driver import AsyncClient

from app.config import RETENTION_DAYS
from app.db.clickhouse import run_command
from app.services.billing import FREE_PLAN


def retention_days(plan: str) -> int:
    """Retention window (days) for a plan; unknown plans get the free window."""
    return RETENTION_DAYS.get(plan, RETENTION_DAYS[FREE_PLAN])


def cutoff_for(plan: str, now: datetime) -> datetime:
    """The oldest timestamp a plan may keep — events strictly before this go."""
    return now - timedelta(days=retention_days(plan))


def build_delete_query(site_id: str, cutoff: datetime) -> tuple[str, dict[str, Any]]:
    """`ALTER TABLE ... DELETE` for one site's expired rows (site-scoped, §9).

    A per-site predicate (not a partition drop) because retention varies by plan,
    so different sites in the same monthly partition have different cutoffs.
    """
    sql = "ALTER TABLE events DELETE WHERE site_id = {site_id:String} AND ts < {cutoff:DateTime}"
    # Bind a tz-AWARE UTC cutoff: a naive datetime is rendered as a bare string
    # that ClickHouse parses in the *server* timezone, shifting the cutoff by
    # the server's UTC offset (same bug as the stats windows — see
    # services/stats.py::_range_params).
    aware_cutoff = cutoff.replace(tzinfo=UTC) if cutoff.tzinfo is None else cutoff.astimezone(UTC)
    return sql, {"site_id": site_id, "cutoff": aware_cutoff}


async def delete_expired_for_site(
    client: AsyncClient, site_id: str, plan: str, now: datetime
) -> datetime:
    """Delete a site's events older than its plan's retention cutoff.

    Returns the cutoff used (for logging). The mutation is submitted async by
    ClickHouse; it never blocks ingestion.
    """
    cutoff = cutoff_for(plan, now)
    sql, params = build_delete_query(site_id, cutoff)
    await run_command(client, sql, params)
    return cutoff
