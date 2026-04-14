"""Make customer_id NOT NULL on funds and users.

Follow-up to 014_customer_tenancy. Seed data populates customer_id
for all rows, so greenfield environments can safely enforce this
constraint. This migration backfills any remaining NULL rows with
the first active customer before applying the constraint.

Revision ID: 015
Revises: 014
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "platform"


def upgrade() -> None:
    # Backfill NULL customer_id rows with the first active customer
    # to prevent constraint violation on environments where seeds
    # haven't fully populated the column.
    conn = op.get_bind()
    first_customer = conn.execute(
        sa.text(f"SELECT id FROM {SCHEMA}.customers WHERE status = 'active' LIMIT 1")
    ).scalar()
    if first_customer:
        conn.execute(
            sa.text(
                f"UPDATE {SCHEMA}.funds SET customer_id = :cid WHERE customer_id IS NULL"
            ),
            {"cid": first_customer},
        )
        conn.execute(
            sa.text(
                f"UPDATE {SCHEMA}.users SET customer_id = :cid WHERE customer_id IS NULL"
            ),
            {"cid": first_customer},
        )

    op.alter_column("funds", "customer_id", nullable=False, schema=SCHEMA)
    op.alter_column("users", "customer_id", nullable=False, schema=SCHEMA)


def downgrade() -> None:
    op.alter_column("users", "customer_id", nullable=True, schema=SCHEMA)
    op.alter_column("funds", "customer_id", nullable=True, schema=SCHEMA)
