"""Orders schema — orders and fills.

Revision ID: 001
Revises: None
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB

# Tables live in the "positions" logical schema, which schema_translate_map
# rewrites to the active fund schema (e.g. fund_alpha) at runtime.
SCHEMA = "positions"


def upgrade() -> None:
    # Orders
    op.create_table(
        "orders",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "filled_quantity",
            sa.Numeric(18, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("limit_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("avg_fill_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("rejection_reason", sa.String(512), nullable=True),
        sa.Column("compliance_results", PG_JSONB(), nullable=True),
        sa.Column("time_in_force", sa.String(8), nullable=False),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_orders_portfolio", "orders", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_orders_state", "orders", ["state"], schema=SCHEMA)
    op.create_index("ix_orders_fund", "orders", ["fund_slug"], schema=SCHEMA)

    # Order fills
    op.create_table(
        "order_fills",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column(
            "order_id",
            PG_UUID(),
            sa.ForeignKey("positions.orders.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "filled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_order_fills_order", "order_fills", ["order_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_order_fills_order", table_name="order_fills", schema=SCHEMA)
    op.drop_table("order_fills", schema=SCHEMA)
    op.drop_index("ix_orders_fund", table_name="orders", schema=SCHEMA)
    op.drop_index("ix_orders_state", table_name="orders", schema=SCHEMA)
    op.drop_index("ix_orders_portfolio", table_name="orders", schema=SCHEMA)
    op.drop_table("orders", schema=SCHEMA)
