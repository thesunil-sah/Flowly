"""CSV export — shape, dataset allowlist, no-PII, and the ownership gate (§9)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ValidationError
from app.core.security import create_access_token
from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, Site
from app.services import export

F = datetime(2026, 7, 1, tzinfo=UTC)
T = datetime(2026, 7, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.column_names = list(rows[0].keys()) if rows else []
        self.result_rows = [tuple(r.values()) for r in rows]


class MockClickHouse:
    def __init__(self, *responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> _Result:
        self.calls.append(sql)
        return _Result(self._responses.pop(0) if self._responses else [])


_OVERVIEW_ROW = [
    {"pageviews": 10, "visitors": 5, "sessions": 6, "bounces": 2, "total_duration": 300}
]


async def test_overview_csv_shape() -> None:
    # overview(compare=True) issues two queries (current + previous window).
    ch = MockClickHouse(_OVERVIEW_ROW, _OVERVIEW_ROW)
    filename, content = await export.build_csv(ch, "pub0", F, T, "overview")
    assert filename.endswith(".csv") and "overview" in filename
    lines = content.strip().splitlines()
    assert lines[0] == "metric,value,previous,change_pct"
    assert any(line.startswith("pageviews,") for line in lines)


async def test_unknown_dataset_is_rejected() -> None:
    with pytest.raises(ValidationError):
        await export.build_csv(MockClickHouse(), "pub0", F, T, "raw_events")


async def test_audience_csv_has_no_pii() -> None:
    ch = MockClickHouse([{"label": "US", "pageviews": 5, "visitors": 3}])
    _filename, content = await export.build_csv(ch, "pub0", F, T, "audience", dimension="country")
    # Aggregated only — never a per-visitor identifier or raw IP.
    assert "visitor_hash" not in content
    assert "ip" not in content.splitlines()[0].lower()
    assert content.splitlines()[0] == "country,pageviews,visitors"


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory() as s:
        owner = Account(email="owner@e.com", username="owner")
        s.add(owner)
        await s.flush()
        owner_id = owner.id
        s.add(Site(account_id=owner_id, site_id="pub0", domain="a.com"))
        other = Account(email="other@e.com", username="other")
        s.add(other)
        await s.flush()
        s.add(Site(account_id=other.id, site_id="foreign", domain="c.com"))
        await s.commit()
    return owner_id


async def test_export_endpoint_returns_csv_for_owned_site(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW, _OVERVIEW_ROW)
    token = create_access_token(owner_id)
    resp = await client.get(
        "/stats/export",
        params={"site_id": "pub0", "dataset": "overview"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]


async def test_export_endpoint_foreign_site_is_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    ch = MockClickHouse(_OVERVIEW_ROW, _OVERVIEW_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(owner_id)
    resp = await client.get(
        "/stats/export",
        params={"site_id": "foreign", "dataset": "overview"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert ch.calls == []  # ownership rejected before any query


async def test_export_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/stats/export", params={"site_id": "pub0"})
    assert resp.status_code == 401
