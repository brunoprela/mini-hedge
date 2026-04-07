"""FX rates table — spot exchange rates for currency conversion.

Revision ID: 004
Revises: 003
Create Date: 2026-04-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("timestamp", "base_currency", "quote_currency"),
        schema="market_data",
    )
    op.create_index(
        "ix_md_fx_rates_pair_time",
        "fx_rates",
        ["base_currency", "quote_currency", "timestamp"],
        schema="market_data",
    )


def downgrade() -> None:
    op.drop_table("fx_rates", schema="market_data")
