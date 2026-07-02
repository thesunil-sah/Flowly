"""Async ClickHouse client (clickhouse-connect).

Connectivity only in Phase 1 — the `events` table and query helpers land in
Phase 3 (ingestion). Client setup lives here; no business rules (CLAUDE.md §3).
"""

from clickhouse_connect import get_async_client
from clickhouse_connect.driver import AsyncClient

from app.config import settings

_client: AsyncClient | None = None


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


async def close_clickhouse() -> None:
    """Close the ClickHouse client (call on app shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
