"""Add risk_counterparties table.

Revision ID: 002
Revises: 001
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "risk_counterparties",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("counterparty_type", sa.String(32), nullable=False),
        sa.Column("credit_rating", sa.String(8), nullable=True),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("netting_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cpty_name",
        "risk_counterparties",
        ["name"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_cpty_name", table_name="risk_counterparties", schema=SCHEMA)
    op.drop_table("risk_counterparties", schema=SCHEMA)
