"""Add liquidity profiles, margin requirements, and counterparty exposure tables.

Revision ID: 003
Revises: 002
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "positions"


def upgrade() -> None:
    # -- Liquidity profiles --
    op.create_table(
        "risk_liquidity_profiles",
        sa.Column("id", PG_UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("total_nav", sa.Numeric(18, 2), nullable=False),
        sa.Column("pct_1_day", sa.Numeric(8, 4), nullable=False),
        sa.Column("pct_1_week", sa.Numeric(8, 4), nullable=False),
        sa.Column("pct_1_month", sa.Numeric(8, 4), nullable=False),
        sa.Column("pct_3_months", sa.Numeric(8, 4), nullable=False),
        sa.Column("pct_illiquid", sa.Numeric(8, 4), nullable=False),
        sa.Column("weighted_days_to_liquidate", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "redemption_coverage_pct",
            sa.Numeric(8, 4),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_liq_portfolio", "risk_liquidity_profiles", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_liq_date", "risk_liquidity_profiles", ["business_date"], schema=SCHEMA)

    # -- Margin requirements --
    op.create_table(
        "risk_margin_requirements",
        sa.Column("id", PG_UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("initial_margin", sa.Numeric(18, 2), nullable=False),
        sa.Column("maintenance_margin", sa.Numeric(18, 2), nullable=False),
        sa.Column("margin_available", sa.Numeric(18, 2), nullable=False),
        sa.Column("margin_excess_deficit", sa.Numeric(18, 2), nullable=False),
        sa.Column("margin_utilization_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "margin_call_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_margin_portfolio", "risk_margin_requirements", ["portfolio_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_margin_date", "risk_margin_requirements", ["business_date"], schema=SCHEMA
    )

    # -- Counterparty exposures --
    op.create_table(
        "risk_counterparty_exposures",
        sa.Column("id", PG_UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("counterparty_id", PG_UUID(), nullable=False),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("gross_exposure", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_exposure", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "collateral_held", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "collateral_posted", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False),
        sa.Column("utilization_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("breach", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cpty_exp_cpty", "risk_counterparty_exposures", ["counterparty_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_cpty_exp_date", "risk_counterparty_exposures", ["business_date"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_cpty_exp_date", table_name="risk_counterparty_exposures", schema=SCHEMA)
    op.drop_index("ix_cpty_exp_cpty", table_name="risk_counterparty_exposures", schema=SCHEMA)
    op.drop_table("risk_counterparty_exposures", schema=SCHEMA)

    op.drop_index("ix_margin_date", table_name="risk_margin_requirements", schema=SCHEMA)
    op.drop_index("ix_margin_portfolio", table_name="risk_margin_requirements", schema=SCHEMA)
    op.drop_table("risk_margin_requirements", schema=SCHEMA)

    op.drop_index("ix_liq_date", table_name="risk_liquidity_profiles", schema=SCHEMA)
    op.drop_index("ix_liq_portfolio", table_name="risk_liquidity_profiles", schema=SCHEMA)
    op.drop_table("risk_liquidity_profiles", schema=SCHEMA)
