"""add username and email_verified_at

Revision ID: c134c38c8923
Revises: 0001_baseline
Create Date: 2026-07-02

Adds the unique `username` and nullable `email_verified_at` columns. `username`
is added nullable first, backfilled from each account's email local-part (so an
already-populated table survives), then made NOT NULL + unique. The backfill is
written in Python so it runs on both Postgres and SQLite (the migration test).
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c134c38c8923"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_usernames() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, email FROM accounts WHERE username IS NULL")).fetchall()
    seen: set[str] = set()
    for row in rows:
        base = re.sub(r"[^a-z0-9_]", "", row.email.split("@")[0].lower())[:32] or "user"
        name, i = base, 1
        while name in seen:
            suffix = str(i)
            name = base[: 32 - len(suffix)] + suffix
            i += 1
        seen.add(name)
        bind.execute(
            sa.text("UPDATE accounts SET username = :u WHERE id = :id"),
            {"u": name, "id": row.id},
        )


def upgrade() -> None:
    op.add_column("accounts", sa.Column("username", sa.String(length=32), nullable=True))
    op.add_column(
        "accounts", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    _backfill_usernames()
    with op.batch_alter_table("accounts") as batch:
        batch.alter_column("username", existing_type=sa.String(length=32), nullable=False)
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_accounts_username", table_name="accounts")
    op.drop_column("accounts", "email_verified_at")
    op.drop_column("accounts", "username")
