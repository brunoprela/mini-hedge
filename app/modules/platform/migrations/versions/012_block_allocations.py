"""Block trade allocations — cross-fund fill distribution.

A block allocation represents a single execution across multiple funds,
with fills distributed pro-rata at the average price.

Revision ID: 012
Revises: 011
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "block_allocations",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("total_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "filled_quantity",
            sa.Numeric(18, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("avg_fill_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False, server_default="market"),
        sa.Column("limit_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("algo_type", sa.String(16), nullable=True),
        sa.Column("algo_params", PG_JSONB(), nullable=True),
        sa.Column("execution_fund_slug", sa.String(64), nullable=True),
        sa.Column("execution_order_id", PG_UUID(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_block_alloc_state",
        "block_allocations",
        ["state"],
        schema="platform",
    )

    op.create_table(
        "allocation_legs",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "block_allocation_id",
            PG_UUID(),
            sa.ForeignKey("platform.block_allocations.id"),
            nullable=False,
        ),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("target_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("target_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "filled_quantity",
            sa.Numeric(18, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("avg_fill_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("allocated_order_id", PG_UUID(), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("compliance_results", PG_JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_alloc_legs_block",
        "allocation_legs",
        ["block_allocation_id"],
        schema="platform",
    )
    op.create_index(
        "ix_platform_alloc_legs_fund",
        "allocation_legs",
        ["fund_slug"],
        schema="platform",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_alloc_legs_fund",
        table_name="allocation_legs",
        schema="platform",
    )
    op.drop_index(
        "ix_platform_alloc_legs_block",
        table_name="allocation_legs",
        schema="platform",
    )
    op.drop_table("allocation_legs", schema="platform")
    op.drop_index(
        "ix_platform_block_alloc_state",
        table_name="block_allocations",
        schema="platform",
    )
    op.drop_table("block_allocations", schema="platform")
