"""Add TCA (Transaction Cost Analysis) support.

Adds arrival price columns to orders and creates the order_tca_results table
for storing cost decomposition analysis.

Revision ID: 004
Revises: 003
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return str(stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA))


def upgrade() -> None:
    schema = _schema()

    # Arrival price columns on orders
    op.add_column(
        "orders",
        sa.Column("arrival_mid_price", sa.Numeric(18, 8), nullable=True),
        schema=schema,
    )
    op.add_column(
        "orders",
        sa.Column("arrival_spread", sa.Numeric(18, 8), nullable=True),
        schema=schema,
    )
    op.add_column(
        "orders",
        sa.Column(
            "arrival_timestamp",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema=schema,
    )

    # TCA results table
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
        # Implementation shortfall
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
        schema=schema,
    )
    op.create_index(
        "ix_tca_order_id",
        "order_tca_results",
        ["order_id"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    op.drop_index("ix_tca_order_id", table_name="order_tca_results", schema=schema)
    op.drop_table("order_tca_results", schema=schema)
    op.drop_column("orders", "arrival_timestamp", schema=schema)
    op.drop_column("orders", "arrival_spread", schema=schema)
    op.drop_column("orders", "arrival_mid_price", schema=schema)
