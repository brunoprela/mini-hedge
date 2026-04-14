"""TCA schema — order transaction cost analysis results.

Revision ID: 001
Revises: None
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "order_tca_results",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("order_id", PG_UUID(), nullable=False, unique=True),
        # Benchmarks
        sa.Column("arrival_mid_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("arrival_spread", sa.Numeric(18, 8), nullable=False),
        sa.Column("vwap_benchmark", sa.Numeric(18, 8), nullable=True),
        # Cost decomposition (basis points)
        sa.Column("total_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("commission_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("spread_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("market_impact_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("timing_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("opportunity_cost_bps", sa.Numeric(12, 4), nullable=False),
        sa.Column("implementation_shortfall_bps", sa.Numeric(12, 4), nullable=False),
        # Participation metrics
        sa.Column("participation_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("execution_duration_seconds", sa.Integer(), nullable=False),
        # Dollar amounts
        sa.Column("total_cost_usd", sa.Numeric(18, 4), nullable=False),
        # Metadata
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_tca_order_id",
        "order_tca_results",
        ["order_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tca_order_id",
        table_name="order_tca_results",
        schema=SCHEMA,
    )
    op.drop_table("order_tca_results", schema=SCHEMA)
