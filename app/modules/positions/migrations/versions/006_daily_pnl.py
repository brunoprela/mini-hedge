"""Add daily P&L snapshot table.

Daily snapshots of position-level P&L, created during EOD processing.
Supports historical P&L queries and reporting.

Revision ID: 006
Revises: 005
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def _get_schema() -> str:
    """Resolve the target schema from Alembic config attributes."""
    from alembic import context as alembic_ctx

    schema = getattr(alembic_ctx.config.attributes, "target_schema", None)
    if schema is None:
        schema = alembic_ctx.config.attributes.get("target_schema", "positions")
    return str(schema)


def upgrade() -> None:
    schema = _get_schema()
    op.create_table(
        "daily_pnl",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("business_date", sa.Date, nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("market_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(18, 8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=False, server_default=sa.text("0")),
        sa.Column("daily_pnl", sa.Numeric(18, 8), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "portfolio_id", "instrument_id", "business_date", name="uq_daily_pnl_position_date"
        ),
        schema=schema,
    )
    op.create_index(
        "ix_pos_daily_pnl_portfolio_date",
        "daily_pnl",
        ["portfolio_id", "business_date"],
        schema=schema,
    )
    op.create_index(
        "ix_pos_daily_pnl_date",
        "daily_pnl",
        ["business_date"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _get_schema()
    op.drop_table("daily_pnl", schema=schema)
