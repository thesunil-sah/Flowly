"""services/sites.py — creation, generation, snippet, and hybrid verification.

Postgres is the in-memory SQLite from conftest; Redis is a real FakeRedis (so the
presence ZSET behaves); ClickHouse is a canned mock (no analytics DB needed).
These lock the pieces the router just wires together.
"""

from typing import Any
from uuid import UUID

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.models.tables import Account
from app.services import sites


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.column_names = list(rows[0].keys()) if rows else []
        self.result_rows = [tuple(r.values()) for r in rows]


class MockClickHouse:
    """Returns one canned result set; records whether it was queried at all."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.calls: list[str] = []

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> _Result:
        self.calls.append(sql)
        return _Result(self._rows)


async def _new_account(session_factory: async_sessionmaker[AsyncSession], email: str) -> UUID:
    async with session_factory() as s:
        acc = Account(email=email, username=email.split("@")[0])
        s.add(acc)
        await s.commit()
        return acc.id


async def test_create_site_normalizes_domain_and_generates_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = await _new_account(session_factory, "a@example.com")
    async with session_factory() as s:
        site = await sites.create_site(s, account_id, "HTTPS://WWW.Example.com/pricing")
    assert site.domain == "example.com"  # scheme/www/path stripped, lowercased
    assert len(site.site_id) == 16 and all(c in "0123456789abcdef" for c in site.site_id)


async def test_create_site_rejects_empty_domain(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = await _new_account(session_factory, "b@example.com")
    async with session_factory() as s:
        with pytest.raises(ValidationError):
            await sites.create_site(s, account_id, "   ")  # normalizes to ""


async def test_duplicate_domain_same_account_conflicts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = await _new_account(session_factory, "c@example.com")
    async with session_factory() as s:
        await sites.create_site(s, account_id, "example.com")
    async with session_factory() as s:
        with pytest.raises(ConflictError):
            await sites.create_site(s, account_id, "www.example.com")  # same host normalized


async def test_same_domain_different_account_allowed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    a1 = await _new_account(session_factory, "d@example.com")
    a2 = await _new_account(session_factory, "e@example.com")
    async with session_factory() as s:
        await sites.create_site(s, a1, "example.com")
    async with session_factory() as s:
        site2 = await sites.create_site(s, a2, "example.com")  # different tenant → fine
    assert site2.domain == "example.com"


async def test_build_snippet_carries_site_id_and_url() -> None:
    snippet = sites.build_snippet("abc123")
    assert 'data-site="abc123"' in snippet
    assert settings.tracker_script_url in snippet


async def test_first_event_seen_redis_short_circuits() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # A live visitor right now -> presence set is non-empty.
    await redis.zadd("active:pub0", {"vh": 4_000_000_000})
    ch = MockClickHouse([])
    assert await sites.first_event_seen(redis, ch, "pub0") is True
    assert ch.calls == []  # Redis hit -> ClickHouse never queried
    await redis.aclose()


async def test_first_event_seen_falls_back_to_clickhouse() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)  # empty presence
    ch = MockClickHouse([{"1": 1}])  # but ClickHouse has an event
    assert await sites.first_event_seen(redis, ch, "pub0") is True
    assert ch.calls  # fallback path was exercised
    await redis.aclose()


async def test_first_event_seen_false_when_nothing_anywhere() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ch = MockClickHouse([])
    assert await sites.first_event_seen(redis, ch, "pub0") is False
    await redis.aclose()
