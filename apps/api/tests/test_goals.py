"""Phase 15 — custom events + conversion goals (first premium feature).

Covers the unforgiving surfaces (§9): entitlement gating (free → 402), ownership
(another account's site → 404), and goal CRUD. The ClickHouse-backed reports
(events / conversions) are exercised against a mock client — the same
`MockClickHouse` idiom as the paywall tests.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, Site

NOW = datetime.now(UTC)


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


def _auth(account_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(account_id)}"}


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: str = "active",
    plan: str = "metered",
    site_id: str = "pub0",
) -> UUID:
    """Seed an account + one site. Defaults to a PAID account (the premium
    surface); pass status="free" for the gating tests."""
    async with session_factory() as s:
        acc = Account(email=f"{site_id}@e.com", username=site_id, plan=plan, status=status)
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id=site_id, domain=f"{site_id}.com"))
        await s.commit()
        return acc.id


def _use_ch(ch: MockClickHouse) -> None:
    app.dependency_overrides[get_clickhouse] = lambda: ch


def _clear_ch() -> None:
    app.dependency_overrides.pop(get_clickhouse, None)


# --- entitlement gate: free accounts can't read the premium surface -------
async def test_events_report_requires_paid(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory, status="free", plan="free")
    ch = MockClickHouse([])
    _use_ch(ch)
    resp = await client.get("/events", params={"site_id": "pub0"}, headers=_auth(acc_id))
    _clear_ch()
    assert resp.status_code == 402  # UpgradeRequiredError
    assert ch.calls == []  # gated before any ClickHouse query


async def test_goals_list_requires_paid(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory, status="free", plan="free")
    resp = await client.get("/goals", params={"site_id": "pub0"}, headers=_auth(acc_id))
    assert resp.status_code == 402


# --- ownership: a paid account can't reach another account's site ---------
async def test_goals_unowned_site_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)  # owns pub0
    await _seed(session_factory, site_id="other")  # a different account owns "other"
    resp = await client.get("/goals", params={"site_id": "other"}, headers=_auth(acc_id))
    assert resp.status_code == 404


# --- goal CRUD ------------------------------------------------------------
async def test_create_and_list_goal(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    body = {"name": "Signup", "kind": "custom", "target": "signup"}
    created = await client.post(
        "/goals", params={"site_id": "pub0"}, json=body, headers=_auth(acc_id)
    )
    assert created.status_code == 201
    assert created.json()["target"] == "signup"

    listed = await client.get("/goals", params={"site_id": "pub0"}, headers=_auth(acc_id))
    assert listed.status_code == 200
    assert [g["name"] for g in listed.json()] == ["Signup"]


async def test_duplicate_goal_conflict(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    body = {"name": "Thanks", "kind": "pageview", "target": "/thank-you"}
    first = await client.post(
        "/goals", params={"site_id": "pub0"}, json=body, headers=_auth(acc_id)
    )
    second = await client.post(
        "/goals", params={"site_id": "pub0"}, json=body, headers=_auth(acc_id)
    )
    assert first.status_code == 201
    assert second.status_code == 409  # same (kind, target) → clean conflict


async def test_delete_goal(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    created = await client.post(
        "/goals",
        params={"site_id": "pub0"},
        json={"name": "Signup", "kind": "custom", "target": "signup"},
        headers=_auth(acc_id),
    )
    goal_id = created.json()["id"]
    deleted = await client.delete(
        f"/goals/{goal_id}", params={"site_id": "pub0"}, headers=_auth(acc_id)
    )
    assert deleted.status_code == 204
    listed = await client.get("/goals", params={"site_id": "pub0"}, headers=_auth(acc_id))
    assert listed.json() == []


async def test_delete_unknown_goal_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    resp = await client.delete(
        f"/goals/{uuid4()}", params={"site_id": "pub0"}, headers=_auth(acc_id)
    )
    assert resp.status_code == 404


# --- ClickHouse-backed reports (mock client) ------------------------------
async def test_events_report_returns_rows(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    ch = MockClickHouse([{"name": "signup", "count": 12, "visitors": 9}])
    _use_ch(ch)
    resp = await client.get("/events", params={"site_id": "pub0"}, headers=_auth(acc_id))
    _clear_ch()
    assert resp.status_code == 200
    assert resp.json()["rows"] == [{"name": "signup", "count": 12, "visitors": 9}]


async def test_goal_conversion_rate(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acc_id = await _seed(session_factory)
    created = await client.post(
        "/goals",
        params={"site_id": "pub0"},
        json={"name": "Signup", "kind": "custom", "target": "signup"},
        headers=_auth(acc_id),
    )
    goal_id = created.json()["id"]
    ch = MockClickHouse([{"conversions": 3, "visitors": 10}])
    _use_ch(ch)
    resp = await client.get(
        f"/goals/{goal_id}/conversions", params={"site_id": "pub0"}, headers=_auth(acc_id)
    )
    _clear_ch()
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["conversions"] == 3
    assert payload["visitors"] == 10
    assert payload["conversion_rate"] == 0.3
