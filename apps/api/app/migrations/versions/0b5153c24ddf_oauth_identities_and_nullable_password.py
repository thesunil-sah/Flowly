"""oauth identities and nullable password

Revision ID: 0b5153c24ddf
Revises: c134c38c8923
Create Date: 2026-07-02

Adds the `identities` table (linked social logins) and makes
`accounts.password_hash` nullable (OAuth-only accounts have no password). The
nullable change uses batch mode so it also runs on SQLite (the migration test).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0b5153c24ddf"
down_revision: str | None = "c134c38c8923"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_user"),
    )
    op.create_index("ix_identities_account_id", "identities", ["account_id"])
    with op.batch_alter_table("accounts") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_identities_account_id", table_name="identities")
    op.drop_table("identities")
