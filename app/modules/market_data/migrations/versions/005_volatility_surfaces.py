"""Volatility surface table — implied vol grid points for options pricing.

Revision ID: 005
Revises: 004
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "volatility_surfaces",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("strike", sa.Numeric(18, 4), nullable=False),
        sa.Column("implied_vol", sa.Numeric(10, 6), nullable=False),
        sa.Column("delta", sa.Numeric(10, 6), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("timestamp", "instrument_id", "expiry", "strike"),
        schema="market_data",
    )
    op.create_index(
        "ix_vs_instrument_expiry",
        "volatility_surfaces",
        ["instrument_id", "expiry"],
        schema="market_data",
    )
    op.create_index(
        "ix_vs_timestamp",
        "volatility_surfaces",
        ["timestamp"],
        schema="market_data",
    )


def downgrade() -> None:
    op.drop_index("ix_vs_timestamp", table_name="volatility_surfaces", schema="market_data")
    op.drop_index("ix_vs_instrument_expiry", table_name="volatility_surfaces", schema="market_data")
    op.drop_table("volatility_surfaces", schema="market_data")
