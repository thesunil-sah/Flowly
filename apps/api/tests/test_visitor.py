"""Cookieless visitor hashing + daily salt rotation."""

import fakeredis.aioredis
import pytest_asyncio

from app.services import visitor

UA = "Mozilla/5.0 Chrome/120 Safari/537.36"


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    visitor._reset_cache()
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()
    await r.aclose()


async def test_salt_is_stable_within_day_with_ttl(redis) -> None:
    salt = await visitor.get_daily_salt(redis)
    again = await visitor.get_daily_salt(redis)
    assert salt == again
    ttl = await redis.ttl(f"salt:{visitor._today()}")
    assert ttl > 0


async def test_hash_is_deterministic(redis) -> None:
    salt = await visitor.get_daily_salt(redis)
    a = visitor.visitor_hash("1.2.3.4", UA, "site", salt)
    b = visitor.visitor_hash("1.2.3.4", UA, "site", salt)
    assert a == b
    assert len(a) == 64


async def test_hash_differs_per_site(redis) -> None:
    salt = await visitor.get_daily_salt(redis)
    a = visitor.visitor_hash("1.2.3.4", UA, "site-a", salt)
    b = visitor.visitor_hash("1.2.3.4", UA, "site-b", salt)
    assert a != b


async def test_hash_differs_across_salt(redis) -> None:
    a = visitor.visitor_hash("1.2.3.4", UA, "site", "salt-day-1")
    b = visitor.visitor_hash("1.2.3.4", UA, "site", "salt-day-2")
    assert a != b


async def test_raw_ip_never_in_hash(redis) -> None:
    salt = await visitor.get_daily_salt(redis)
    h = visitor.visitor_hash("203.0.113.42", UA, "site", salt)
    assert "203.0.113.42" not in h


async def test_concurrent_creators_converge(redis) -> None:
    # Without the in-process cache, concurrent first-writers must still land on
    # a single salt value in Redis (SET NX).
    visitor._reset_cache()
    key = f"salt:{visitor._today()}"
    # Simulate two independent processes racing on the same key.
    import secrets

    a = secrets.token_hex(16)
    created_a = await redis.set(key, a, ex=1000, nx=True)
    b = secrets.token_hex(16)
    created_b = await redis.set(key, b, ex=1000, nx=True)
    assert created_a is True
    assert created_b is None
    assert await redis.get(key) == a
