"""Async ClickHouse client + `events` table helpers (clickhouse-connect).

Client setup plus the analytics sink for ingestion: the `events` DDL, an
idempotent initializer, and a batched insert helper. No business rules live here
(CLAUDE.md §3) — the ingest service builds rows; the batch writer calls
`insert_events`.

Run ``uv run python -m app.db.clickhouse --init`` once to create the table.
"""

from typing import Annotated, Any

from clickhouse_connect import get_async_client
from clickhouse_connect.driver import AsyncClient
from fastapi import Depends

from app.config import settings

_client: AsyncClient | None = None

# Canonical column order. The ingest row dicts, `insert_events`, and any query
# must all agree on this — keep them in lockstep.
EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "site_id",
    "ts",
    "path",
    "referrer",
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "country",
    "region",
    "device",
    "browser",
    "os",
    "visitor_hash",
    "screen_w",
)

# Append-only, partitioned by month, ordered for by-site_id queries.
# Empty-string defaults (not Nullable) keep inserts fast; `event_id` is present
# so a future move to ReplacingMergeTree (dedupe on it) is cheap.
CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id      UUID,
    site_id       String,
    ts            DateTime64(3, 'UTC') DEFAULT now64(3),
    path          String,
    referrer      String,
    source        LowCardinality(String),
    utm_source    String,
    utm_medium    String,
    utm_campaign  String,
    country       LowCardinality(String),
    region        String,
    device        LowCardinality(String),
    browser       LowCardinality(String),
    os            LowCardinality(String),
    visitor_hash  String,
    screen_w      UInt16
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (site_id, ts)
"""


async def get_clickhouse() -> AsyncClient:
    """Return a process-wide async ClickHouse client (lazily constructed)."""
    global _client
    if _client is None:
        _client = await get_async_client(
            host=settings.clickhouse_host,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_db,
        )
    return _client


ClickHouseDep = Annotated[AsyncClient, Depends(get_clickhouse)]


async def init_events_table(client: AsyncClient | None = None) -> None:
    """Create the `events` table if it does not exist (idempotent)."""
    ch = client or await get_clickhouse()
    await ch.command(CREATE_EVENTS_TABLE)


async def insert_events(client: AsyncClient, rows: list[dict[str, Any]]) -> None:
    """Bulk-insert event rows. `rows` are dicts keyed by `EVENT_COLUMNS`.

    Values must already be the right Python types (UUID, datetime, int, str) —
    the batch writer coerces them off the Redis stream before calling this.
    """
    if not rows:
        return
    matrix = [[row[col] for col in EVENT_COLUMNS] for row in rows]
    await client.insert("events", matrix, column_names=list(EVENT_COLUMNS))


async def close_clickhouse() -> None:
    """Close the ClickHouse client (call on app shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def _main() -> None:
    import sys

    if "--init" in sys.argv:
        await init_events_table()
        print("events table ready")
    else:
        print("usage: python -m app.db.clickhouse --init")
    await close_clickhouse()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
