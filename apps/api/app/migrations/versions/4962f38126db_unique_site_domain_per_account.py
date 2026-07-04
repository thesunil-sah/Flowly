"""unique site domain per account

Revision ID: 4962f38126db
Revises: 0b5153c24ddf
Create Date: 2026-07-04

Adds a UNIQUE(account_id, domain) constraint to `sites` so a duplicate domain
under one account is rejected by the database — the real arbiter behind
create_site's pre-check, which alone is not race-safe. Uses batch mode so it
also runs on SQLite (the migration test).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "4962f38126db"
down_revision: str | None = "0b5153c24ddf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.create_unique_constraint("uq_site_account_domain", ["account_id", "domain"])


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.drop_constraint("uq_site_account_domain", type_="unique")
