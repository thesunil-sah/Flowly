"""/public/{token} — the shared read-only dashboard (§8/§9).

Key assertions: a live token serves its site's stats with no auth; an unknown or
revoked token 404s; the badge flag tracks the owner's effective plan; and a token
maps only to its own site (no cross-site leak on the public surface).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, ShareToken, Site


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


async def _seed_share(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    token: str = "tok-abc",
    plan: str = "pro",
    status: str = "active",
    trial_ends_at: datetime | None = None,
    revoked: bool = False,
    domain: str = "a.com",
    site_id: str = "pub0",
) -> str:
    async with session_factory() as s:
        owner = Account(
            email=f"{token}@e.com",
            username=token,
            plan=plan,
            status=status,
            trial_ends_at=trial_ends_at,
        )
        s.add(owner)
        await s.flush()
        site = Site(account_id=owner.id, site_id=site_id, domain=domain)
        s.add(site)
        await s.flush()
        st = ShareToken(token=token, site_id=site.id)
        if revoked:
            st.revoked_at = datetime.now(UTC)
        s.add(st)
        await s.commit()
    return token


async def test_public_overview_resolves_live_token(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token = await _seed_share(session_factory)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    resp = await client.get(f"/public/{token}/overview")  # no auth header
    assert resp.status_code == 200
    assert resp.json()["pageviews"]["value"] == 10


async def test_public_unknown_token_is_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    resp = await client.get("/public/nope/overview")
    assert resp.status_code == 404


async def test_public_revoked_token_is_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token = await _seed_share(session_factory, token="revoked-tok", revoked=True)
    ch = MockClickHouse(_OVERVIEW_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    resp = await client.get(f"/public/{token}/overview")
    assert resp.status_code == 404
    assert ch.calls == []  # rejected before any query


async def test_public_meta_badge_true_for_free_owner(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # A lapsed trial (trial ended, no active sub) is effectively free.
    token = await _seed_share(
        session_factory,
        token="free-tok",
        plan="pro",
        status="trialing",
        trial_ends_at=datetime.now(UTC) - timedelta(days=1),
    )
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse()
    resp = await client.get(f"/public/{token}")
    assert resp.status_code == 200
    assert resp.json() == {"domain": "a.com", "show_badge": True}


async def test_public_meta_badge_false_for_paid_owner(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token = await _seed_share(session_factory, token="paid-tok", plan="pro", status="active")
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse()
    resp = await client.get(f"/public/{token}")
    assert resp.json()["show_badge"] is False


async def test_public_token_maps_only_to_its_site(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_share(session_factory, token="tok-a", domain="a.com", site_id="pubA")
    await _seed_share(session_factory, token="tok-b", domain="b.com", site_id="pubB")
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse()
    ra = await client.get("/public/tok-a")
    rb = await client.get("/public/tok-b")
    assert ra.json()["domain"] == "a.com"
    assert rb.json()["domain"] == "b.com"
