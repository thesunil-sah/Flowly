"""Live service: presence ZSET, pub/sub, and the ownership query.

Redis is fakeredis (async, same loop as the test). `get_owned_site` runs against
the in-memory SQLite from conftest.
"""

import asyncio
from uuid import uuid4

import app.db.redis as redis_mod
import fakeredis.aioredis
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.tables import Account, Site
from app.services import live


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


async def test_count_counts_distinct_visitors_in_window(redis) -> None:
    now = 1_000.0
    await live.mark_active(redis, "s", "h1", now)
    await live.mark_active(redis, "s", "h2", now)
    assert await live.count_active(redis, "s", now) == 2
    # Same visitor again within the day -> still one member (ZADD overwrites).
    await live.mark_active(redis, "s", "h1", now + 1)
    assert await live.count_active(redis, "s", now + 1) == 2


async def test_count_evicts_past_the_window(redis) -> None:
    now = 1_000.0
    await live.mark_active(redis, "s", "h1", now)
    later = now + live.LIVE_WINDOW_SECONDS + 5
    assert await live.count_active(redis, "s", later) == 0


async def test_write_side_eviction_bounds_zset_with_no_reader(redis) -> None:
    # A busy but unwatched site must not grow forever: each write evicts stale.
    await live.mark_active(redis, "s", "old", 0.0)
    await live.mark_active(redis, "s", "new", 10_000.0)
    # 'old' is far outside the window at the second write's time -> evicted.
    assert await redis.zcard("active:s") == 1


async def test_mark_active_sets_ttl(redis) -> None:
    await live.mark_active(redis, "s", "h", 1_000.0)
    ttl = await redis.ttl("active:s")
    assert 0 < ttl <= live.LIVE_WINDOW_SECONDS + 61


async def test_subscribe_receives_published_event(redis, monkeypatch) -> None:
    # subscribe_events uses the shared client; point it at this fake.
    monkeypatch.setattr(redis_mod, "_client", redis)
    received: list[dict[str, object]] = []
    ready = asyncio.Event()

    async def _on_ready() -> None:
        ready.set()

    async def consume() -> None:
        async for event in live.subscribe_events("s", on_ready=_on_ready):
            received.append(event)
            break

    task = asyncio.create_task(consume())
    await asyncio.wait_for(ready.wait(), 2)  # subscription is live
    await live.publish_event(redis, "s", {"path": "/x", "device": "desktop"})
    await asyncio.wait_for(task, 2)

    # Got the real message (not the subscribe-confirmation frame, which is filtered).
    assert received == [{"path": "/x", "device": "desktop"}]


async def test_record_and_publish(redis, monkeypatch) -> None:
    # One call updates presence AND publishes in a single pipeline.
    monkeypatch.setattr(redis_mod, "_client", redis)
    received: list[dict[str, object]] = []
    ready = asyncio.Event()

    async def _on_ready() -> None:
        ready.set()

    async def consume() -> None:
        async for event in live.subscribe_events("s", on_ready=_on_ready):
            received.append(event)
            break

    task = asyncio.create_task(consume())
    await asyncio.wait_for(ready.wait(), 2)
    await live.record_and_publish(redis, "s", "hash1", {"path": "/z"}, 1_000.0)
    await asyncio.wait_for(task, 2)

    assert await redis.zcard("active:s") == 1
    assert received == [{"path": "/z"}]


async def test_get_owned_site(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        acc = Account(email="owner@example.com", username="owner")
        s.add(acc)
        await s.flush()
        acc_id = acc.id
        s.add(Site(account_id=acc_id, site_id="pub", domain="ex.com"))
        await s.commit()

    async with session_factory() as s:
        assert await live.get_owned_site(s, "pub", acc_id) is not None
        # A different account does not own it (the #1 leak path).
        assert await live.get_owned_site(s, "pub", uuid4()) is None
        # Unknown site.
        assert await live.get_owned_site(s, "missing", acc_id) is None
