"""/sites — authed, ownership-scoped onboarding (list, create, verify)."""

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


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    """Create an owner with two sites plus a foreign account with one site."""
    async with session_factory() as s:
        owner = Account(email="owner@example.com", username="owner")
        s.add(owner)
        await s.flush()
        owner_id = owner.id
        s.add(Site(account_id=owner_id, site_id="pub0", domain="a.com"))
        s.add(Site(account_id=owner_id, site_id="pub1", domain="b.com"))

        other = Account(email="other@example.com", username="other")
        s.add(other)
        await s.flush()
        s.add(Site(account_id=other.id, site_id="foreign", domain="c.com"))
        await s.commit()
    return owner_id


async def test_list_sites_is_ownership_scoped(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    resp = await client.get("/sites", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    site_ids = {row["site_id"] for row in resp.json()}
    assert site_ids == {"pub0", "pub1"}  # foreign site excluded


async def test_list_sites_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/sites")
    assert resp.status_code == 401


async def test_list_sites_includes_snippet(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    resp = await client.get("/sites", headers={"Authorization": f"Bearer {token}"})
    rows = {row["site_id"]: row for row in resp.json()}
    assert 'data-site="pub0"' in rows["pub0"]["snippet"]  # canonical to_site_out shape


async def test_create_site_returns_normalized_domain_and_snippet(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    resp = await client.post(
        "/sites",
        json={"domain": "HTTPS://WWW.NewSite.com/pricing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["domain"] == "newsite.com"
    assert f'data-site="{body["site_id"]}"' in body["snippet"]


async def test_create_site_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/sites", json={"domain": "example.com"})
    assert resp.status_code == 401


async def test_create_duplicate_domain_same_account_is_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    # "a.com" is already seeded for this owner.
    resp = await client.post("/sites", json={"domain": "www.a.com"}, headers=headers)
    assert resp.status_code == 409


async def test_create_invalid_domain_is_422(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    resp = await client.post(
        "/sites", json={"domain": "   "}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_status_owned_site_returns_connected(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    # Empty Redis (from the client fixture) + empty ClickHouse -> not connected.
    ch = MockClickHouse([])
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(owner_id)
    resp = await client.get("/sites/pub0/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"connected": False}


async def test_status_foreign_site_is_404_before_any_query(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    ch = MockClickHouse([{"1": 1}])
    app.dependency_overrides[get_clickhouse] = lambda: ch
    token = create_access_token(owner_id)
    resp = await client.get("/sites/foreign/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    assert ch.calls == []  # ownership rejected before ClickHouse was touched


async def test_status_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/sites/pub0/status")
    assert resp.status_code == 401
