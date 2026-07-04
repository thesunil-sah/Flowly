"""billing: subscription fields + processed_stripe_events

Revision ID: c7f1b2f13d02
Revises: 4962f38126db
Create Date: 2026-07-04

Phase 7 billing schema: adds `subscriptions.stripe_price_id` and
`subscriptions.cancel_at_period_end`, and creates the `processed_stripe_events`
webhook-idempotency ledger. Column adds use batch mode so the migration also
runs on SQLite (the migration test).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7f1b2f13d02"
down_revision: str | None = "4962f38126db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(sa.Column("stripe_price_id", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column(
                "cancel_at_period_end",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    op.create_table(
        "processed_stripe_events",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_stripe_events")
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("cancel_at_period_end")
        batch.drop_column("stripe_price_id")
