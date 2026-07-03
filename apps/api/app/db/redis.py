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
    """Return a process-wide Redis client (lazily constructed).

    Uses redis-py's default 5s socket read timeout — the right fail-fast for the
    API hot path (rate-limit checks, live pub/sub). A blocking stream consumer
    needs a longer read timeout than its BLOCK window; it must use `make_client`.
    """
    global _client
    if _client is None:
        _client = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


def make_client(socket_timeout: float | None = None) -> Redis:
    """Build a NEW (non-shared) Redis client with an explicit read timeout.

    For a dedicated **blocking** consumer like the batch writer: its
    `XREADGROUP ... BLOCK` holds the socket for the block window, so the client's
    socket read timeout must exceed that window or every idle cycle raises a
    spurious `TimeoutError`. (redis-py 8 forces a 5s default when the timeout is
    left `None`, so pass a concrete value here.)
    """
    return from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=socket_timeout,
    )


async def get_redis() -> Redis:
    """FastAPI dependency returning the shared Redis client."""
    return get_client()


async def close_redis() -> None:
    """Close the Redis client (call on app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
