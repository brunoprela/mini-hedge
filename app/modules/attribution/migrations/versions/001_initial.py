"""Attribution schema — Brinson-Fachler, risk-based, cumulative.

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

SCHEMA = "positions"


def upgrade() -> None:
    # Brinson-Fachler results
    op.create_table(
        "attr_brinson_fachler",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("portfolio_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("benchmark_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("active_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("total_allocation", sa.Numeric(10, 6), nullable=False),
        sa.Column("total_selection", sa.Numeric(10, 6), nullable=False),
        sa.Column("total_interaction", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_bf_portfolio", "attr_brinson_fachler", ["portfolio_id"], schema=SCHEMA)
    op.create_index(
        "ix_bf_period", "attr_brinson_fachler", ["period_start", "period_end"], schema=SCHEMA
    )

    # Brinson-Fachler sector breakdown
    op.create_table(
        "attr_brinson_fachler_sectors",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("bf_result_id", PG_UUID(), nullable=False),
        sa.Column("sector", sa.String(50), nullable=False),
        sa.Column("portfolio_weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("benchmark_weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("portfolio_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("benchmark_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("allocation_effect", sa.Numeric(10, 6), nullable=False),
        sa.Column("selection_effect", sa.Numeric(10, 6), nullable=False),
        sa.Column("interaction_effect", sa.Numeric(10, 6), nullable=False),
        sa.Column("total_effect", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_bf_sector_result", "attr_brinson_fachler_sectors", ["bf_result_id"], schema=SCHEMA
    )

    # Risk-based attribution
    op.create_table(
        "attr_risk_based",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("systematic_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("idiosyncratic_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("systematic_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_rb_portfolio", "attr_risk_based", ["portfolio_id"], schema=SCHEMA)
    op.create_index(
        "ix_rb_period", "attr_risk_based", ["period_start", "period_end"], schema=SCHEMA
    )

    # Risk factor contributions
    op.create_table(
        "attr_risk_factor_contributions",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("rb_result_id", PG_UUID(), nullable=False),
        sa.Column("factor", sa.String(100), nullable=False),
        sa.Column("factor_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("portfolio_exposure", sa.Numeric(10, 6), nullable=False),
        sa.Column("pnl_contribution", sa.Numeric(18, 4), nullable=False),
        sa.Column("pct_of_total", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_rfc_result", "attr_risk_factor_contributions", ["rb_result_id"], schema=SCHEMA
    )

    # Cumulative attribution (Carino linked)
    op.create_table(
        "attr_cumulative",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("cumulative_portfolio_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("cumulative_benchmark_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("cumulative_active_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("cumulative_allocation", sa.Numeric(10, 6), nullable=False),
        sa.Column("cumulative_selection", sa.Numeric(10, 6), nullable=False),
        sa.Column("cumulative_interaction", sa.Numeric(10, 6), nullable=False),
        sa.Column("periods", PG_JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_cum_portfolio", "attr_cumulative", ["portfolio_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_cum_portfolio", table_name="attr_cumulative", schema=SCHEMA)
    op.drop_table("attr_cumulative", schema=SCHEMA)
    op.drop_index("ix_rfc_result", table_name="attr_risk_factor_contributions", schema=SCHEMA)
    op.drop_table("attr_risk_factor_contributions", schema=SCHEMA)
    op.drop_index("ix_rb_period", table_name="attr_risk_based", schema=SCHEMA)
    op.drop_index("ix_rb_portfolio", table_name="attr_risk_based", schema=SCHEMA)
    op.drop_table("attr_risk_based", schema=SCHEMA)
    op.drop_index("ix_bf_sector_result", table_name="attr_brinson_fachler_sectors", schema=SCHEMA)
    op.drop_table("attr_brinson_fachler_sectors", schema=SCHEMA)
    op.drop_index("ix_bf_period", table_name="attr_brinson_fachler", schema=SCHEMA)
    op.drop_index("ix_bf_portfolio", table_name="attr_brinson_fachler", schema=SCHEMA)
    op.drop_table("attr_brinson_fachler", schema=SCHEMA)
