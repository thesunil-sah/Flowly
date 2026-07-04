"""Runs the real Alembic migration to catch ORM/migration drift (D12).

Applied against a throwaway SQLite file so it needs no external service; the
definitive apply against Postgres happens via `alembic upgrade head` in dev/CI.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

# Repo layout: tests/ -> apps/api/ (where alembic.ini lives).
_API_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "accounts",
    "sites",
    "subscriptions",
    "share_tokens",
    "onboarding_emails",
}


@pytest.fixture
def alembic_config(tmp_path, monkeypatch) -> tuple[Config, Path]:
    db_path = tmp_path / "migration_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    return cfg, db_path


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def test_upgrade_creates_tables(alembic_config) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= _tables(db_path)


def test_downgrade_is_reversible(alembic_config) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert not (EXPECTED_TABLES & _tables(db_path))
