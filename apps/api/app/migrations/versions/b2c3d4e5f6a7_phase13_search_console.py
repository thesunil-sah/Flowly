"""phase 13: search console connections + metrics

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-07

Phase 13 Search Console schema:
- `search_console_connections` — one GSC property + refresh token per site (1:1).
- `search_metrics` — daily Search Analytics rows (query, page, clicks,
  impressions, position); idempotent per (site, date).

New tables only (additive) — runs on the SQLite migration test too.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_console_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("property_url", sa.String(length=255), nullable=False),
        sa.Column("refresh_token", sa.String(length=512), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_console_connections_site_id",
        "search_console_connections",
        ["site_id"],
        unique=True,
    )

    op.create_table(
        "search_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("page", sa.String(length=2048), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("position", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_metrics_site_id", "search_metrics", ["site_id"], unique=False)
    op.create_index("ix_search_metrics_date", "search_metrics", ["date"], unique=False)
    # The read reports + the per-day idempotent delete both filter on (site, date).
    op.create_index(
        "ix_search_metrics_site_date", "search_metrics", ["site_id", "date"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_search_metrics_site_date", table_name="search_metrics")
    op.drop_index("ix_search_metrics_date", table_name="search_metrics")
    op.drop_index("ix_search_metrics_site_id", table_name="search_metrics")
    op.drop_table("search_metrics")
    op.drop_index(
        "ix_search_console_connections_site_id", table_name="search_console_connections"
    )
    op.drop_table("search_console_connections")
