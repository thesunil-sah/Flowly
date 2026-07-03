"""Service-layer tests with a mocked ClickHouse.

No fake-ClickHouse library exists, so a small `MockClickHouse` returns canned
result sets in call order (mirroring `test_batch_writer.py`). These lock the
Python-side arithmetic the SQL doesn't do: bounce ratio, compare deltas, and
time-series zero-filling.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.exceptions import ValidationError
from app.services import stats

FROM = datetime(2026, 7, 1, tzinfo=UTC)
TO = datetime(2026, 7, 5, tzinfo=UTC)  # 4 days -> day buckets


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.column_names = list(rows[0].keys()) if rows else []
        self.result_rows = [tuple(r.values()) for r in rows]


class MockClickHouse:
    """Returns queued result sets in call order; records the queries it saw."""

    def __init__(self, *responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> _Result:
        self.calls.append((sql, parameters or {}))
        return _Result(self._responses.pop(0))


def _overview_row(**kw: int) -> dict[str, int]:
    base = {"pageviews": 0, "visitors": 0, "sessions": 0, "bounces": 0, "total_duration": 0}
    return base | kw


async def test_overview_derives_bounce_rate_and_duration() -> None:
    ch = MockClickHouse(
        [_overview_row(pageviews=100, visitors=40, sessions=50, bounces=20, total_duration=5000)]
    )
    out = await stats.overview(ch, "s", FROM, TO, compare=False)
    assert out.pageviews.value == 100
    assert out.visitors.value == 40
    assert out.bounce_rate.value == 40.0  # 20/50
    assert out.avg_duration.value == 100  # 5000/50
    assert out.pageviews.previous is None and out.pageviews.change_pct is None


async def test_overview_zero_sessions_is_safe() -> None:
    ch = MockClickHouse([_overview_row()])  # all zeros
    out = await stats.overview(ch, "s", FROM, TO, compare=False)
    assert out.bounce_rate.value == 0.0  # no divide-by-zero
    assert out.avg_duration.value == 0


async def test_overview_compare_computes_change_pct() -> None:
    current = _overview_row(pageviews=120, visitors=60, sessions=50, bounces=10, total_duration=0)
    previous = _overview_row(pageviews=100, visitors=50, sessions=40, bounces=10, total_duration=0)
    ch = MockClickHouse([current], [previous])
    out = await stats.overview(ch, "s", FROM, TO, compare=True)
    assert out.pageviews.previous == 100
    assert out.pageviews.change_pct == 20.0  # (120-100)/100
    assert len(ch.calls) == 2  # current + previous window


async def test_overview_compare_against_zero_is_none() -> None:
    current = _overview_row(pageviews=50, sessions=10)
    previous = _overview_row()  # empty prior period
    out = await stats.overview(MockClickHouse([current], [previous]), "s", FROM, TO, compare=True)
    assert out.pageviews.previous == 0
    assert out.pageviews.change_pct is None  # % against zero is undefined, not ∞


async def test_timeseries_zero_fills_missing_buckets() -> None:
    # DB returns data for only 2 of the 4 days; the gaps must come back as zeros.
    # clickhouse-connect returns toStartOf* buckets as NAIVE datetimes (UTC) —
    # mirror that here so the service's tz handling is exercised faithfully.
    rows = [
        {"bucket": datetime(2026, 7, 1), "pageviews": 10, "visitors": 5},
        {"bucket": datetime(2026, 7, 3), "pageviews": 7, "visitors": 3},
    ]
    out = await stats.timeseries(MockClickHouse(rows), "s", FROM, TO)
    assert out.interval == "day"
    assert [p.bucket.day for p in out.points] == [1, 2, 3, 4]
    assert [p.pageviews for p in out.points] == [10, 0, 7, 0]


async def test_pages_metric_label_matches_kind() -> None:
    rows = [{"label": "/pricing", "count": 12, "visitors": 9}]
    top = await stats.pages(MockClickHouse(rows), "s", FROM, TO, "top", 10)
    assert top.metric == "pageviews"
    entry = await stats.pages(MockClickHouse(rows), "s", FROM, TO, "entry", 10)
    assert entry.metric == "sessions"


async def test_sources_runs_two_queries() -> None:
    src = [{"label": "google", "pageviews": 30, "visitors": 20}]
    utm = [
        {
            "utm_source": "newsletter",
            "utm_medium": "email",
            "utm_campaign": "july",
            "pageviews": 5,
            "visitors": 4,
        }
    ]
    out = await stats.sources(MockClickHouse(src, utm), "s", FROM, TO, 10)
    assert out.sources[0].label == "google"
    assert out.utm[0].utm_campaign == "july"


async def test_audience_rejects_unknown_dimension() -> None:
    with pytest.raises(ValidationError):
        await stats.audience(MockClickHouse([]), "s", FROM, TO, "ip_address", 10)


async def test_pages_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        await stats.pages(MockClickHouse([]), "s", FROM, TO, "sideways", 10)
