"""Redis fixed-window rate limiter.

Home-grown (no new dependency — slowapi isn't in CLAUDE.md §5). Used on
`/auth/login` this phase; the generic `enforce_rate_limit` helper is reused
for per-site `/collect` limiting in Phase 3.
"""

from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import RateLimitError

# Login: 5 attempts per 15 minutes per (client IP + normalized email).
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60


async def _incr_window(redis: Redis, key: str, window_seconds: int) -> int:
    """Increment a fixed-window counter and return the new count.

    The window starts on the first hit (TTL set when the counter is created)
    and the whole key expires when it lapses.
    """
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count


async def enforce_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Increment a fixed-window counter; raise RateLimitError past `limit`."""
    count = await _incr_window(redis, key, window_seconds)
    if count > limit:
        raise RateLimitError()


async def enforce_login_rate_limit(redis: Redis, client_ip: str, email: str) -> None:
    key = f"ratelimit:login:{client_ip}:{email}"
    await enforce_rate_limit(redis, key, LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)


async def is_rate_limited(redis: Redis, site_id: str, ip: str) -> bool:
    """Non-raising per-(site_id, IP) check for the public /collect hot path.

    Returns True when the caller is over the limit. It must NOT raise: an
    over-limit pageview is dropped silently (the endpoint still returns 202),
    so a flooding client can't detect the filter. This is a blunt abuse
    backstop, not precise metering (that arrives with plan limits in Phase 7).
    """
    key = f"ratelimit:collect:{site_id}:{ip}"
    count = await _incr_window(redis, key, settings.collect_rate_window)
    return count > settings.collect_rate_limit
