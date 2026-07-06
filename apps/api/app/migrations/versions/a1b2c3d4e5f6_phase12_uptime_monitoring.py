"""phase 12: uptime monitors + incidents

Revision ID: a1b2c3d4e5f6
Revises: f3a9c1d47b20
Create Date: 2026-07-06

Phase 12 uptime schema:
- `uptime_monitors` — current up/down state per site (1:1) + the fail streak
  that powers retry-before-alarm.
- `uptime_incidents` — one row per down period; the open row (resolved_at NULL)
  is the alert-idempotency key (down/up emailed once each).

Plain `create_table` (no batch mode needed — new tables only) so it also runs on
the SQLite migration test.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f3a9c1d47b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uptime_monitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fail_streak", sa.Integer(), nullable=False),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uptime_monitors_site_id", "uptime_monitors", ["site_id"], unique=True)

    op.create_table(
        "uptime_incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cause", sa.String(length=32), nullable=False),
        sa.Column("notified_down", sa.Boolean(), nullable=False),
        sa.Column("notified_up", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uptime_incidents_site_id", "uptime_incidents", ["site_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_uptime_incidents_site_id", table_name="uptime_incidents")
    op.drop_table("uptime_incidents")
    op.drop_index("ix_uptime_monitors_site_id", table_name="uptime_monitors")
    op.drop_table("uptime_monitors")
