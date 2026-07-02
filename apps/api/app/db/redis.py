"""Async Redis client (redis-py).

Client setup only. Used this phase by the login rate limiter; live counters,
pub/sub, usage metering and the ingest stream arrive in later phases. The
client is created lazily and connects on first command, so importing this
module does not require a running Redis.
"""

from redis.asyncio import Redis, from_url

from app.config import settings

_client: Redis | None = None


def get_client() -> Redis:
    """Return a process-wide Redis client (lazily constructed)."""
    global _client
    if _client is None:
        _client = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def get_redis() -> Redis:
    """FastAPI dependency returning the shared Redis client."""
    return get_client()


async def close_redis() -> None:
    """Close the Redis client (call on app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
