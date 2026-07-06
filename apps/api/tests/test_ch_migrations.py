"""ClickHouse migration convention (Phase 11).

No live ClickHouse: a fake client records the DDL. The safety contract is that
every migration is idempotent (`IF NOT EXISTS`) so re-running the whole list is a
no-op, and `run_migrations` applies them all in order.
"""

from app.db.ch_migrations import CH_MIGRATIONS, run_migrations


class _FakeClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def command(self, sql: str) -> None:
        self.commands.append(sql)


async def test_every_migration_is_idempotent() -> None:
    # The whole point of the convention: re-running must be safe (§3).
    for name, sql in CH_MIGRATIONS:
        assert "IF NOT EXISTS" in sql, name


async def test_run_migrations_applies_all_in_order() -> None:
    client = _FakeClient()
    applied = await run_migrations(client)  # type: ignore[arg-type]
    assert applied == [name for name, _ in CH_MIGRATIONS]
    assert len(client.commands) == len(CH_MIGRATIONS)
    # Phase 11 adds city + language.
    joined = " ".join(client.commands)
    assert "city String" in joined
    assert "language LowCardinality(String)" in joined


async def test_rerun_is_a_noop_on_already_migrated_schema() -> None:
    # Idempotency means a second run issues the same statements (all no-ops),
    # never errors or partial state.
    client = _FakeClient()
    await run_migrations(client)  # type: ignore[arg-type]
    first = list(client.commands)
    await run_migrations(client)  # type: ignore[arg-type]
    assert client.commands == first * 2
