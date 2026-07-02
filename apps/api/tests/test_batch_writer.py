"""Batch writer: type coercion, bulk insert + XACK, and crash reclaim.

ClickHouse is mocked (no fake-ClickHouse lib); we assert on the rows it would
receive. Redis is real fakeredis, which supports XREADGROUP/XAUTOCLAIM.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import fakeredis.aioredis
import pytest_asyncio

from app.models.events import CollectEvent
from app.services import ingest, visitor
from app.workers import batch_writer as bw

UA = "Mozilla/5.0 Chrome/120 Safari/537.36"
STREAM = "stream:events"


class MockClickHouse:
    """Records insert() calls the way clickhouse-connect's AsyncClient is called."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[list[Any]], list[str]]] = []

    async def insert(
        self, table: str, matrix: list[list[Any]], column_names: list[str] | None = None
    ) -> None:
        self.calls.append((table, matrix, column_names or []))

    def rows_as_dicts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _table, matrix, cols in self.calls:
            out.extend(dict(zip(cols, row)) for row in matrix)
        return out


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    visitor._reset_cache()
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


async def _seed(redis, ip: str = "9.9.9.9") -> None:
    ev = CollectEvent.model_validate(
        {"site_id": "demo", "path": "/p", "referrer": "https://google.com", "screen_w": 1440}
    )
    await ingest.ingest_event(ev, ip, UA, "https://demo.example", redis)


async def test_drain_inserts_and_acks(redis) -> None:
    await _seed(redis)
    await _seed(redis, ip="8.8.8.8")
    await bw.ensure_group(redis)
    ch = MockClickHouse()

    inserted = await bw.drain_once(redis, ch)

    assert inserted == 2
    assert len(ch.calls) == 1  # a single bulk insert, not one-per-row
    assert ch.calls[0][0] == "events"
    # Everything acked -> no pending entries left.
    pending = await redis.xpending(STREAM, bw.GROUP)
    assert pending["pending"] == 0


async def test_types_are_coerced(redis) -> None:
    await _seed(redis)
    await bw.ensure_group(redis)
    ch = MockClickHouse()
    await bw.drain_once(redis, ch)

    row = ch.rows_as_dicts()[0]
    assert isinstance(row["event_id"], UUID)
    assert isinstance(row["ts"], datetime)
    assert isinstance(row["screen_w"], int)
    assert row["screen_w"] == 1440


async def test_malformed_entry_is_dropped_not_wedged(redis) -> None:
    await bw.ensure_group(redis)
    # A junk entry missing required typed fields.
    await redis.xadd(STREAM, {"event_id": "not-a-uuid", "ts": "nope"})
    ch = MockClickHouse()

    inserted = await bw.drain_once(redis, ch)

    assert inserted == 0  # nothing valid to insert
    # But it was acked (dropped), so it can't be redelivered forever.
    pending = await redis.xpending(STREAM, bw.GROUP)
    assert pending["pending"] == 0


async def test_reclaim_reprocesses_stranded_entries(redis, monkeypatch) -> None:
    await _seed(redis)
    await bw.ensure_group(redis)
    # Simulate a consumer that read a message then crashed before acking.
    await redis.xreadgroup(bw.GROUP, "dead-consumer", {STREAM: ">"}, count=10)
    assert (await redis.xpending(STREAM, bw.GROUP))["pending"] == 1

    # Reclaim anything idle >= 0ms for the test.
    monkeypatch.setattr(bw, "RECLAIM_MIN_IDLE_MS", 0)
    ch = MockClickHouse()
    reclaimed = await bw.reclaim_pending(redis, ch)

    assert reclaimed == 1
    assert len(ch.calls) == 1
    assert (await redis.xpending(STREAM, bw.GROUP))["pending"] == 0
