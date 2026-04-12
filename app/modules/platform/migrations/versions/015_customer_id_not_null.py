"""Make customer_id NOT NULL on funds and users.

Follow-up to 014_customer_tenancy. Seed data populates customer_id
for all rows, so greenfield environments can safely enforce this
constraint. Production environments should verify the backfill
completed before applying this migration.

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
    op.alter_column("funds", "customer_id", nullable=False, schema=SCHEMA)
    op.alter_column("users", "customer_id", nullable=False, schema=SCHEMA)


def downgrade() -> None:
    op.alter_column("users", "customer_id", nullable=True, schema=SCHEMA)
    op.alter_column("funds", "customer_id", nullable=True, schema=SCHEMA)
