"""Market data schema — price time series.

Revision ID: 001
Revises: None
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS market_data")

    op.create_table(
        "prices",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("bid", sa.Numeric(18, 8), nullable=False),
        sa.Column("ask", sa.Numeric(18, 8), nullable=False),
        sa.Column("mid", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(18, 2), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("timestamp", "instrument_id"),
        schema="market_data",
    )
    op.create_index(
        "ix_md_prices_instrument_time",
        "prices",
        ["instrument_id", "timestamp"],
        schema="market_data",
    )


def downgrade() -> None:
    op.drop_table("prices", schema="market_data")
    op.execute("DROP SCHEMA IF EXISTS market_data")
