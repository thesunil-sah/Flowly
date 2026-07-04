"""Shared `[from, to)` window parsing for stats-serving routes (§3).

The authed dashboard (`routers/stats.py`) and the public shareable dashboard
(`routers/public.py`) resolve the query window identically, so the dependency
lives here rather than being duplicated (or one router importing the other).
All storage/query time is UTC; naive inputs are treated as UTC (§4).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Query

from app.core.exceptions import ValidationError

# Default lookback when no range is given, and the widest queryable span (a
# query-cost guard — per-plan retention enforcement is Phase 9's job).
DEFAULT_RANGE_DAYS = 7
MAX_RANGE_DAYS = 372


def stats_range(
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query(alias="to")] = None,
) -> tuple[datetime, datetime]:
    """Resolve + validate the [from, to) window; default to the last 7 days.

    Naive inputs are treated as UTC. `to` is exclusive. Rejects an inverted or
    over-wide range with 422.
    """

    def _utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

    to_v = _utc(to) if to else datetime.now(UTC)
    from_v = _utc(from_) if from_ else to_v - timedelta(days=DEFAULT_RANGE_DAYS)
    if from_v >= to_v:
        raise ValidationError("`from` must be before `to`.")
    if to_v - from_v > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationError(f"Range exceeds the {MAX_RANGE_DAYS}-day maximum.")
    return from_v, to_v


RangeDep = Annotated[tuple[datetime, datetime], Depends(stats_range)]
