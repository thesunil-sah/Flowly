"""phase 8: email opt-out, share tokens, onboarding ledger

Revision ID: f3a9c1d47b20
Revises: c7f1b2f13d02
Create Date: 2026-07-04

Phase 8 growth schema:
- `accounts.email_opt_out` — unsubscribe flag for non-transactional email.
- `share_tokens` — public read-only dashboard share links (revocable).
- `onboarding_emails` — per-(account, step) sent ledger (idempotency).

The column add uses batch mode so the migration also runs on SQLite (the
migration test).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a9c1d47b20"
down_revision: str | None = "c7f1b2f13d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(
            sa.Column(
                "email_opt_out",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "share_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_share_tokens_token", "share_tokens", ["token"], unique=True)
    op.create_index("ix_share_tokens_site_id", "share_tokens", ["site_id"], unique=False)

    op.create_table(
        "onboarding_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "step", name="uq_onboarding_account_step"),
    )
    op.create_index(
        "ix_onboarding_emails_account_id", "onboarding_emails", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_emails_account_id", table_name="onboarding_emails")
    op.drop_table("onboarding_emails")
    op.drop_index("ix_share_tokens_site_id", table_name="share_tokens")
    op.drop_index("ix_share_tokens_token", table_name="share_tokens")
    op.drop_table("share_tokens")
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("email_opt_out")
