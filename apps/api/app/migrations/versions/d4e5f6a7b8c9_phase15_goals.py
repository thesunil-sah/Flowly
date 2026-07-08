"""phase 15: conversion goals

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-07

Phase 15 (first premium feature — custom events + conversion goals): a `goals`
table holding one row per conversion goal (a pageview path or a named custom
event) per site. Conversion rates are computed at read time from ClickHouse, so
only the goal *definition* is stored here.

Additive table only (batch mode so it runs on the SQLite migration test too).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "kind", "target", name="uq_goal_site_target"),
    )
    op.create_index(op.f("ix_goals_site_id"), "goals", ["site_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_goals_site_id"), table_name="goals")
    op.drop_table("goals")
