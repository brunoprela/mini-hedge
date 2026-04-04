"""Risk engine schema — snapshots, VaR, stress tests, factor exposures.

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
    # Risk snapshots
    op.create_table(
        "risk_snapshots",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("nav", sa.Numeric(18, 4), nullable=False),
        sa.Column("var_95_1d", sa.Numeric(18, 4), nullable=False),
        sa.Column("var_99_1d", sa.Numeric(18, 4), nullable=False),
        sa.Column("expected_shortfall_95", sa.Numeric(18, 4), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(18, 6), nullable=False),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_risk_snap_portfolio",
        "risk_snapshots",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_risk_snap_time",
        "risk_snapshots",
        ["snapshot_at"],
        schema=SCHEMA,
    )

    # VaR results
    op.create_table(
        "risk_var_results",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("confidence_level", sa.Float(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("var_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("var_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("expected_shortfall", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_var_portfolio",
        "risk_var_results",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_var_time",
        "risk_var_results",
        ["calculated_at"],
        schema=SCHEMA,
    )

    # VaR contributions
    op.create_table(
        "risk_var_contributions",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("var_result_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(20), nullable=False),
        sa.Column("weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("marginal_var", sa.Numeric(18, 4), nullable=False),
        sa.Column("component_var", sa.Numeric(18, 4), nullable=False),
        sa.Column("pct_contribution", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_var_contrib_result",
        "risk_var_contributions",
        ["var_result_id"],
        schema=SCHEMA,
    )

    # Stress test results
    op.create_table(
        "risk_stress_results",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("scenario_name", sa.String(100), nullable=False),
        sa.Column("scenario_type", sa.String(20), nullable=False),
        sa.Column("shocks", PG_JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("total_pnl_impact", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_pct_change", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_stress_portfolio",
        "risk_stress_results",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_stress_time",
        "risk_stress_results",
        ["calculated_at"],
        schema=SCHEMA,
    )

    # Stress position impacts
    op.create_table(
        "risk_stress_position_impacts",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("stress_result_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(20), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("stressed_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("pnl_impact", sa.Numeric(18, 4), nullable=False),
        sa.Column("pct_change", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_stress_impact_result",
        "risk_stress_position_impacts",
        ["stress_result_id"],
        schema=SCHEMA,
    )

    # Factor exposures
    op.create_table(
        "risk_factor_exposures",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("snapshot_id", PG_UUID(), nullable=False),
        sa.Column("factor", sa.String(30), nullable=False),
        sa.Column("factor_name", sa.String(100), nullable=False),
        sa.Column("beta", sa.Numeric(10, 6), nullable=False),
        sa.Column("exposure_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("pct_of_total", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_factor_snapshot",
        "risk_factor_exposures",
        ["snapshot_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_factor_snapshot",
        table_name="risk_factor_exposures",
        schema=SCHEMA,
    )
    op.drop_table("risk_factor_exposures", schema=SCHEMA)
    op.drop_index(
        "ix_stress_impact_result",
        table_name="risk_stress_position_impacts",
        schema=SCHEMA,
    )
    op.drop_table("risk_stress_position_impacts", schema=SCHEMA)
    op.drop_index(
        "ix_stress_time",
        table_name="risk_stress_results",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_stress_portfolio",
        table_name="risk_stress_results",
        schema=SCHEMA,
    )
    op.drop_table("risk_stress_results", schema=SCHEMA)
    op.drop_index(
        "ix_var_contrib_result",
        table_name="risk_var_contributions",
        schema=SCHEMA,
    )
    op.drop_table("risk_var_contributions", schema=SCHEMA)
    op.drop_index(
        "ix_var_time",
        table_name="risk_var_results",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_var_portfolio",
        table_name="risk_var_results",
        schema=SCHEMA,
    )
    op.drop_table("risk_var_results", schema=SCHEMA)
    op.drop_index(
        "ix_risk_snap_time",
        table_name="risk_snapshots",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_risk_snap_portfolio",
        table_name="risk_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("risk_snapshots", schema=SCHEMA)
