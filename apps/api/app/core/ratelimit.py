"""Redis fixed-window rate limiter.

Home-grown (no new dependency — slowapi isn't in CLAUDE.md §5). Used on
`/auth/login` this phase; the generic `enforce_rate_limit` helper is reused
for per-site `/collect` limiting in Phase 3.
"""

from redis.asyncio import Redis

from app.core.exceptions import RateLimitError

# Login: 5 attempts per 15 minutes per (client IP + normalized email).
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60


async def enforce_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Increment a fixed-window counter; raise RateLimitError past `limit`.

    The window starts on the first hit (TTL set when the counter is created)
    and the whole key expires when it lapses.
    """
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        raise RateLimitError()


async def enforce_login_rate_limit(redis: Redis, client_ip: str, email: str) -> None:
    key = f"ratelimit:login:{client_ip}:{email}"
    await enforce_rate_limit(redis, key, LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)
