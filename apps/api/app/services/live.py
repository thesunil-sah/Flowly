"""Live traffic — presence counting + pub/sub fan-out (CLAUDE.md §9 headline).

Redis is the source of truth for "right now"; this module never touches
ClickHouse. Two Redis structures per site:

  - ``active:{site_id}``  ZSET of ``visitor_hash`` scored by unix timestamp —
    who is online in the last ``LIVE_WINDOW_SECONDS``.
  - ``live:{site_id}``    pub/sub channel carrying each event to connected
    dashboards.

`mark_active` bounds the ZSET on every write (evict stale members + set a key
EXPIRE) so a busy-but-unwatched site can't grow without limit and a fully idle
site self-cleans. The ingest hot path calls `mark_active` + `publish_event`
best-effort; the WebSocket router consumes `subscribe_events` + `count_active`.

All I/O is Redis-only except `get_owned_site`, the one Postgres lookup that
enforces tenant isolation before a socket is allowed to stream a site.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_client
from app.models.tables import Site

# A visitor is "online" if seen within this window; the ZSET key outlives the
# window by a buffer so a lone visitor's entry isn't dropped a hair early.
LIVE_WINDOW_SECONDS = 300
_EXPIRE_BUFFER_SECONDS = 60


def _active_key(site_id: str) -> str:
    return f"active:{site_id}"


def _channel(site_id: str) -> str:
    return f"live:{site_id}"


def _queue_presence(pipe: object, site_id: str, visitor_hash: str, now: float) -> None:
    """Queue the presence commands (ZADD + evict + EXPIRE) onto a pipeline.

    Shared by `mark_active` and `record_and_publish` so the window/eviction
    semantics live in one place.
    """
    key = _active_key(site_id)
    cutoff = now - LIVE_WINDOW_SECONDS
    pipe.zadd(key, {visitor_hash: now})  # type: ignore[attr-defined]
    pipe.zremrangebyscore(key, "-inf", cutoff)  # type: ignore[attr-defined]
    pipe.expire(key, LIVE_WINDOW_SECONDS + _EXPIRE_BUFFER_SECONDS)  # type: ignore[attr-defined]


async def mark_active(redis: Redis, site_id: str, visitor_hash: str, now: float) -> None:
    """Record a visitor as active now; evict stale members; bound the key.

    ZADD + ZREMRANGEBYSCORE + EXPIRE run in one pipeline so the ingest hot path
    pays a single round-trip (CLAUDE.md §9 — /collect returns in milliseconds).
    """
    async with redis.pipeline(transaction=False) as pipe:
        _queue_presence(pipe, site_id, visitor_hash, now)
        await pipe.execute()


async def record_and_publish(
    redis: Redis, site_id: str, visitor_hash: str, payload: dict[str, object], now: float
) -> None:
    """Presence update + live publish for one event in a single pipeline.

    The ingest hot path calls this instead of `mark_active` + `publish_event`
    separately, collapsing what would be two round-trips into one (CLAUDE.md §9).
    """
    async with redis.pipeline(transaction=False) as pipe:
        _queue_presence(pipe, site_id, visitor_hash, now)
        pipe.publish(_channel(site_id), json.dumps(payload))
        await pipe.execute()


async def count_active(redis: Redis, site_id: str, now: float) -> int:
    """Number of visitors online in the last window.

    Eviction-inclusive: it drops stale members first, so an idle-but-watched
    site reports a correctly decaying count. Not a pure getter.
    """
    key = _active_key(site_id)
    cutoff = now - LIVE_WINDOW_SECONDS
    await redis.zremrangebyscore(key, "-inf", cutoff)
    return await redis.zcard(key)


async def publish_event(redis: Redis, site_id: str, payload: dict[str, object]) -> None:
    """Fan one event out to every dashboard subscribed to the site's channel."""
    await redis.publish(_channel(site_id), json.dumps(payload))


async def subscribe_events(
    site_id: str,
    on_ready: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Yield each event published to a site's live channel, decoded.

    Owns its own pub/sub connection off the shared client and always tears it
    down. `ignore_subscribe_messages` drops the subscribe-confirmation frame;
    we also filter defensively so only real messages are yielded.

    `on_ready` (if given) is awaited exactly once, *after* the subscription is
    live but *before* the first message is read. The WS router uses it to send
    the initial count snapshot, so no event can slip through the gap between
    snapshot and subscribe (CLAUDE.md Phase 4 — subscribe before snapshot).
    """
    pubsub = get_client().pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(_channel(site_id))
    try:
        if on_ready is not None:
            await on_ready()
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            yield json.loads(message["data"])
    finally:
        # `aclose()` must run even if `unsubscribe` raises on a dead connection,
        # or the pub/sub connection leaks (one per dropped socket).
        try:
            await pubsub.unsubscribe(_channel(site_id))
        finally:
            await pubsub.aclose()


async def get_owned_site(session: AsyncSession, site_id: str, account_id: UUID) -> Site | None:
    """Return the site iff it exists AND belongs to this account (tenant scope).

    Filtering by site_id alone is not enough (CLAUDE.md §9 — the #1 data-leak
    path); the account_id predicate is what enforces ownership.
    """
    return await session.scalar(
        select(Site).where(Site.site_id == site_id, Site.account_id == account_id)
    )


async def list_account_sites(session: AsyncSession, account_id: UUID) -> Sequence[Site]:
    """All of an account's sites, oldest first (ownership-scoped)."""
    result = await session.scalars(
        select(Site).where(Site.account_id == account_id).order_by(Site.created_at)
    )
    return result.all()
