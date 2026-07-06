"""GET /stats/... — auth + the ownership gate (the #1 leak path, §9).

The key assertions: a site the caller doesn't own returns 404 **before** any
ClickHouse query runs, and unauthenticated requests are rejected. ClickHouse is
mocked so the happy path needs no live analytics DB.
"""

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, Site


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


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory() as s:
        owner = Account(email="owner@example.com", username="owner")
        s.add(owner)
        await s.flush()
        owner_id = owner.id
        s.add(Site(account_id=owner_id, site_id="pub0", domain="a.com"))

        other = Account(email="other@example.com", username="other")
        s.add(other)
        await s.flush()
        s.add(Site(account_id=other.id, site_id="foreign", domain="c.com"))
        await s.commit()
    return owner_id


async def test_overview_returns_metrics_for_owned_site(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    ch = MockClickHouse(_OVERVIEW_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(owner_id)

    resp = await client.get(
        "/stats/overview", params={"site_id": "pub0"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pageviews"]["value"] == 10
    assert body["bounce_rate"]["value"] == round(2 / 6 * 100, 1)


async def test_foreign_site_is_404_before_any_query(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    ch = MockClickHouse(_OVERVIEW_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(owner_id)

    resp = await client.get(
        "/stats/overview",
        params={"site_id": "foreign"},  # owned by the other account
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert ch.calls == []  # ownership rejected before ClickHouse was touched


async def test_unknown_site_is_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    token = create_access_token(owner_id)
    resp = await client.get(
        "/stats/overview",
        params={"site_id": "does-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_stats_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/stats/overview", params={"site_id": "pub0"})
    assert resp.status_code == 401


async def test_inverted_range_is_422(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    token = create_access_token(owner_id)
    resp = await client.get(
        "/stats/overview",
        params={"site_id": "pub0", "from": "2026-07-08T00:00:00Z", "to": "2026-07-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# --- Phase 11: the paid-tier city gate --------------------------------------
_BREAKDOWN_ROW = [{"label": "Paris", "pageviews": 3, "visitors": 2}]


async def _seed_account(
    session_factory: async_sessionmaker[AsyncSession], plan: str, status: str, site_id: str
) -> UUID:
    async with session_factory() as s:
        acc = Account(
            email=f"{site_id}@example.com", username=site_id, plan=plan, status=status
        )
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id=site_id, domain=f"{site_id}.com"))
        await s.commit()
        return acc.id


async def test_city_dimension_gated_for_free_account(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed_account(session_factory, "free", "active", "freesite")
    ch = MockClickHouse(_BREAKDOWN_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(acc_id)
    resp = await client.get(
        "/stats/audience",
        params={"site_id": "freesite", "dimension": "city"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402  # UpgradeRequiredError
    assert ch.calls == []  # gated before any ClickHouse query ran


async def test_city_dimension_allowed_for_paid_account(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed_account(session_factory, "pro", "active", "prosite")
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_BREAKDOWN_ROW)
    token = create_access_token(acc_id)
    resp = await client.get(
        "/stats/audience",
        params={"site_id": "prosite", "dimension": "city"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["label"] == "Paris"


async def test_language_dimension_is_free(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed_account(session_factory, "free", "active", "langsite")
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_BREAKDOWN_ROW)
    token = create_access_token(acc_id)
    resp = await client.get(
        "/stats/audience",
        params={"site_id": "langsite", "dimension": "language"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200  # language is NOT gated
