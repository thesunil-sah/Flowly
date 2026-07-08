"""ClickHouse forward migrations for the `events` table (§3).

Alembic is Postgres-only, so ClickHouse schema changes live here as an **ordered,
idempotent** list of DDL statements. The rules (mirror them when adding one):

  1. Every statement is idempotent — use `ADD COLUMN IF NOT EXISTS` (and the like)
     so re-running the whole list is a no-op. There is no "current version"
     bookkeeping; idempotency IS the safety mechanism.
  2. Append new migrations to the END of `CH_MIGRATIONS`, never reorder or edit a
     shipped one (an edited past migration won't re-run on installs that already
     applied it).
  3. Keep `db/clickhouse.py::CREATE_EVENTS_TABLE` in sync so a FRESH install gets
     the columns at create time; existing installs get them from these ALTERs.

Run once per deploy: ``uv run python -m app.db.clickhouse --migrate`` (runs
`--init` first, then these in order). Safe to run repeatedly.
"""

from clickhouse_connect.driver import AsyncClient

# (name, sql) in apply order. `name` is for logging only — ordering is by list
# position. Phase 11 adds city (paid audience report) + language (from the
# tracker's navigator.language). Phase 15 adds event_type + name for custom
# events / conversion goals (a pageview is `event_type='pageview'`, so existing
# rows read correctly against the DEFAULT).
CH_MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "0001_add_city",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS city String",
    ),
    (
        "0002_add_language",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS language LowCardinality(String)",
    ),
    (
        "0003_add_event_type",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS "
        "event_type LowCardinality(String) DEFAULT 'pageview'",
    ),
    (
        "0004_add_event_name",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS name String",
    ),
)


async def run_migrations(client: AsyncClient) -> list[str]:
    """Apply every migration in order (idempotent). Returns the names applied."""
    applied: list[str] = []
    for name, sql in CH_MIGRATIONS:
        await client.command(sql)
        applied.append(name)
    return applied
