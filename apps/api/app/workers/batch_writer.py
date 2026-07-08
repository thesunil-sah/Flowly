"""Batch writer — drains the Redis ingest stream into ClickHouse.

Runs as its own process (``uv run python -m app.workers.batch_writer``). It reads
`stream:events` through a Redis **consumer group**, bulk-inserts each batch into
ClickHouse, and acknowledges only after a successful insert.

Crash-safety (at-least-once): a message read by `XREADGROUP >` moves to the
group's Pending Entries List and is NOT redelivered by `>` if this process dies
before `XACK`. So on startup and periodically we `XAUTOCLAIM` idle pending
entries and reprocess them — nothing is silently lost. A crash between insert and
`XACK` can reprocess a batch, causing rare duplicates (accepted; `event_id` makes
a future ReplacingMergeTree dedupe cheap).
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from clickhouse_connect.driver import AsyncClient
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.db.clickhouse import close_clickhouse, get_clickhouse, init_events_table, insert_events
from app.db.redis import make_client
from app.services.ingest import STREAM_KEY

logger = logging.getLogger("flowly.batch_writer")

GROUP = "batch_writer"
CONSUMER = "worker-1"
BATCH_COUNT = 500
BLOCK_MS = 5000
# The client's socket read timeout must exceed BLOCK_MS, or an idle blocking
# XREADGROUP (which holds the socket for the whole window) trips a spurious
# TimeoutError every cycle. The headroom lets the server's empty reply land
# first while a genuinely dead connection still times out and is logged.
_READ_TIMEOUT_S = BLOCK_MS / 1000 + 5
# Only reclaim entries idle longer than this (i.e. a crashed/stuck consumer).
RECLAIM_MIN_IDLE_MS = 60_000
# Sweep the pending list every N idle/loop iterations.
RECLAIM_EVERY = 20

_stop = asyncio.Event()


def _coerce_row(fields: dict[str, str]) -> dict[str, Any]:
    """Rebuild a typed ClickHouse row from a string-only stream entry.

    Raises KeyError/ValueError on a malformed entry so the caller can drop it.
    """
    return {
        "event_id": UUID(fields["event_id"]),
        "site_id": fields.get("site_id", ""),
        "ts": datetime.fromisoformat(fields["ts"]),
        # Default keeps pre-Phase-15 stream entries (no event_type field) coercing
        # as pageviews.
        "event_type": fields.get("event_type") or "pageview",
        "name": fields.get("name", ""),
        "path": fields.get("path", ""),
        "referrer": fields.get("referrer", ""),
        "source": fields.get("source", ""),
        "utm_source": fields.get("utm_source", ""),
        "utm_medium": fields.get("utm_medium", ""),
        "utm_campaign": fields.get("utm_campaign", ""),
        "country": fields.get("country", ""),
        "region": fields.get("region", ""),
        "city": fields.get("city", ""),
        "device": fields.get("device", ""),
        "browser": fields.get("browser", ""),
        "os": fields.get("os", ""),
        "language": fields.get("language", ""),
        "visitor_hash": fields.get("visitor_hash", ""),
        "screen_w": int(fields.get("screen_w") or 0),
    }


async def _process(
    redis: Redis, ch: AsyncClient, messages: list[tuple[str, dict[str, str]]]
) -> int:
    """Coerce → bulk-insert → XACK a batch. Returns the number of rows inserted.

    Malformed entries are dropped (acked without insert) so they can't wedge the
    stream. If the insert raises, nothing is acked — the batch stays pending for
    a later reclaim/retry.
    """
    rows: list[dict[str, Any]] = []
    good_ids: list[str] = []
    poison_ids: list[str] = []
    for msg_id, fields in messages:
        try:
            rows.append(_coerce_row(fields))
            good_ids.append(msg_id)
        except (KeyError, ValueError) as exc:
            logger.warning("dropping malformed event %s: %s", msg_id, exc)
            poison_ids.append(msg_id)

    if rows:
        await insert_events(ch, rows)  # may raise -> caller leaves batch pending

    ack_ids = good_ids + poison_ids
    if ack_ids:
        await redis.xack(STREAM_KEY, GROUP, *ack_ids)
    return len(rows)


async def ensure_group(redis: Redis) -> None:
    """Create the consumer group at id 0 (drains any pre-existing backlog)."""
    try:
        await redis.xgroup_create(STREAM_KEY, GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def reclaim_pending(redis: Redis, ch: AsyncClient) -> int:
    """Reprocess idle pending entries left by a crashed consumer. Returns count."""
    total = 0
    cursor = "0-0"
    while True:
        cursor, messages, _deleted = await redis.xautoclaim(
            STREAM_KEY,
            GROUP,
            CONSUMER,
            min_idle_time=RECLAIM_MIN_IDLE_MS,
            start_id=cursor,
            count=BATCH_COUNT,
        )
        if messages:
            total += await _process(redis, ch, messages)
        if not messages or cursor == "0-0":
            break
    return total


async def drain_once(redis: Redis, ch: AsyncClient) -> int:
    """One blocking read + process cycle. Returns rows inserted this cycle."""
    resp = await redis.xreadgroup(
        GROUP, CONSUMER, {STREAM_KEY: ">"}, count=BATCH_COUNT, block=BLOCK_MS
    )
    inserted = 0
    if resp:
        for _stream, messages in resp:
            inserted += await _process(redis, ch, messages)
    return inserted


async def run() -> None:
    # A dedicated client (not the shared get_client) so its read timeout can
    # exceed the blocking-read window without changing the API's fail-fast client.
    redis = make_client(socket_timeout=_READ_TIMEOUT_S)
    ch = await get_clickhouse()
    await init_events_table(ch)
    await ensure_group(redis)
    await reclaim_pending(redis, ch)  # recover anything a prior crash stranded

    logger.info("batch_writer started; draining %s", STREAM_KEY)
    iteration = 0
    try:
        while not _stop.is_set():
            try:
                await drain_once(redis, ch)
            except Exception:
                # Insert/transport failure: leave the batch pending, back off.
                logger.exception("drain cycle failed; retrying")
                await asyncio.sleep(1)
            iteration += 1
            if iteration % RECLAIM_EVERY == 0:
                await reclaim_pending(redis, ch)
    finally:
        await redis.aclose()
        await close_clickhouse()
        logger.info("batch_writer stopped")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    import signal

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop.set)
        except (NotImplementedError, AttributeError):
            # Windows event loop doesn't support signal handlers; Ctrl-C still
            # raises KeyboardInterrupt and unwinds the run() finally block.
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
