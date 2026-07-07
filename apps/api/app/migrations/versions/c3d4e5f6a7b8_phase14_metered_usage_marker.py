"""phase 14: durable metered-usage high-water mark on subscriptions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-07

Phase 14 usage-push hardening: the "already reported to Stripe's Billing Meter"
high-water mark moves from Redis to Postgres so it can't be evicted independently
of the ephemeral usage counter (which would let the delta-push re-push a whole
month → Stripe double-bills, §9). Two additive columns on `subscriptions`:
- `metered_usage_reported` — views already pushed for the current period.
- `metered_usage_period`   — the calendar month ("YYYYMM") that mark belongs to.

Additive columns only (batch mode so it runs on the SQLite migration test too).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(
            sa.Column("metered_usage_reported", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("metered_usage_period", sa.String(length=6), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("metered_usage_period")
        batch.drop_column("metered_usage_reported")
