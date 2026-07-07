"""Phase 14 paywall — the free-over-limit lock across every read surface.

A free account past FREE_MONTHLY_VIEWS is *locked*: its dashboard reads (stats,
CSV export, live) and its side doors (public share, digest) return the typed 402
`account_locked` / are skipped. The one hard rule (§9): **ingestion never gates**
— `/collect` keeps returning 202 while locked so the charts stay hole-free.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import fakeredis.aioredis
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import FREE_MONTHLY_VIEWS
from app.core.security import create_access_token
from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, ShareToken, Site
from app.services import billing

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


_OVERVIEW_ROW = [
    {"pageviews": 10, "visitors": 5, "sessions": 6, "bounces": 2, "total_duration": 300}
]


def _auth(account_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(account_id)}"}


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: str = "free",
    plan: str = "free",
    site_id: str = "pub0",
) -> UUID:
    async with session_factory() as s:
        acc = Account(email=f"{site_id}@e.com", username=site_id, plan=plan, status=status)
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id=site_id, domain=f"{site_id}.com"))
        await s.commit()
        return acc.id


async def _lock(redis: fakeredis.aioredis.FakeRedis, account_id: UUID) -> None:
    """Push the account's month usage past the free limit."""
    await redis.set(billing.usage_key(account_id, NOW), FREE_MONTHLY_VIEWS + 1)


# --- dashboard reads are gated ------------------------------------------
async def test_stats_locked_free_account_gets_402(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    acc_id = await _seed(session_factory)
    await _lock(redis_client, acc_id)
    ch = MockClickHouse(_OVERVIEW_ROW)
    app.dependency_overrides[get_clickhouse] = lambda: ch
    resp = await client.get("/stats/overview", params={"site_id": "pub0"}, headers=_auth(acc_id))
    app.dependency_overrides.pop(get_clickhouse, None)
    assert resp.status_code == 402
    assert resp.json()["code"] == "account_locked"
    assert ch.calls == []  # gated before any ClickHouse query


async def test_stats_free_under_limit_ok(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    acc_id = await _seed(session_factory)
    await redis_client.set(billing.usage_key(acc_id, NOW), FREE_MONTHLY_VIEWS)  # at limit, not over
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    resp = await client.get("/stats/overview", params={"site_id": "pub0"}, headers=_auth(acc_id))
    app.dependency_overrides.pop(get_clickhouse, None)
    assert resp.status_code == 200


async def test_export_locked_free_account_gets_402(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    acc_id = await _seed(session_factory)
    await _lock(redis_client, acc_id)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    resp = await client.get(
        "/stats/export", params={"site_id": "pub0", "dataset": "overview"}, headers=_auth(acc_id)
    )
    app.dependency_overrides.pop(get_clickhouse, None)
    assert resp.status_code == 402  # export follows the lock (not a side door)


async def test_metered_account_not_locked(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    # A paying account way over the free allotment is billed, never walled off.
    acc_id = await _seed(session_factory, status="active", plan="metered")
    await redis_client.set(billing.usage_key(acc_id, NOW), FREE_MONTHLY_VIEWS * 100)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    resp = await client.get("/stats/overview", params={"site_id": "pub0"}, headers=_auth(acc_id))
    app.dependency_overrides.pop(get_clickhouse, None)
    assert resp.status_code == 200


# --- side door: public share follows the lock ---------------------------
async def test_public_share_follows_lock(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    acc_id = await _seed(session_factory)
    async with session_factory() as s:
        site = await s.scalar(select(Site).where(Site.site_id == "pub0"))
        s.add(ShareToken(token="tok-lock", site_id=site.id))
        await s.commit()
    await _lock(redis_client, acc_id)
    app.dependency_overrides[get_clickhouse] = lambda: MockClickHouse(_OVERVIEW_ROW)
    data = await client.get("/public/tok-lock/overview")
    meta = await client.get("/public/tok-lock")  # meta stays open (paused state)
    app.dependency_overrides.pop(get_clickhouse, None)
    assert data.status_code == 402  # locked owner → share link paused
    assert meta.status_code == 200


# --- the hard rule: ingestion is NEVER gated ----------------------------
async def test_collect_still_ingests_while_locked(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    acc_id = await _seed(session_factory)
    # Wire the site->account map so metering would run, and lock the account.
    await billing.cache_site_account(redis_client, "pub0", acc_id)
    await _lock(redis_client, acc_id)
    body = '{"site_id":"pub0","path":"/x"}'
    resp = await client.post(
        "/collect",
        content=body,
        headers={
            "content-type": "text/plain",
            "origin": "https://pub0.com",
            "user-agent": "Mozilla/5.0",
        },
    )
    assert resp.status_code == 202  # §9 — never drop data, even while locked
