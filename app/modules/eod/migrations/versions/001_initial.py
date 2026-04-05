"""EOD processing schema — runs, steps, finalized prices, NAV, P&L, recon.

Revision ID: 001
Revises: None
Create Date: 2026-04-05
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

SCHEMA = "eod"


def upgrade() -> None:
    # --- EOD Runs ---
    op.create_table(
        "runs",
        sa.Column(
            "run_id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True
        ),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_successful", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.create_index("ix_eod_runs_date", "runs", ["business_date"], schema=SCHEMA)
    op.create_index("ix_eod_runs_fund", "runs", ["fund_slug"], schema=SCHEMA)

    # --- EOD Run Steps ---
    op.create_table(
        "run_steps",
        sa.Column("run_id", PG_UUID(), sa.ForeignKey(f"{SCHEMA}.runs.run_id"), primary_key=True),
        sa.Column("step", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", PG_JSONB(), nullable=True),
        schema=SCHEMA,
    )

    # --- Finalized Prices ---
    op.create_table(
        "finalized_prices",
        sa.Column("instrument_id", sa.String(32), primary_key=True),
        sa.Column("business_date", sa.Date(), primary_key=True),
        sa.Column("close_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "finalized_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finalized_by", sa.String(64), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_finalized_prices_date", "finalized_prices", ["business_date"], schema=SCHEMA
    )

    # --- NAV Snapshots ---
    op.create_table(
        "nav_snapshots",
        sa.Column("portfolio_id", PG_UUID(), primary_key=True),
        sa.Column("business_date", sa.Date(), primary_key=True),
        sa.Column("gross_market_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_market_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("accrued_fees", sa.Numeric(18, 2), nullable=False),
        sa.Column("nav", sa.Numeric(18, 2), nullable=False),
        sa.Column("nav_per_share", sa.Numeric(18, 8), nullable=False),
        sa.Column("shares_outstanding", sa.Numeric(18, 8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    # --- P&L Snapshots ---
    op.create_table(
        "pnl_snapshots",
        sa.Column("portfolio_id", PG_UUID(), primary_key=True),
        sa.Column("business_date", sa.Date(), primary_key=True),
        sa.Column("total_realized_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_unrealized_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("details", PG_JSONB(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    # --- Reconciliation Results ---
    op.create_table(
        "reconciliation_results",
        sa.Column("portfolio_id", PG_UUID(), primary_key=True),
        sa.Column("business_date", sa.Date(), primary_key=True),
        sa.Column("total_positions", sa.Integer(), nullable=False),
        sa.Column("matched_positions", sa.Integer(), nullable=False),
        sa.Column("is_clean", sa.Boolean(), nullable=False),
        sa.Column("breaks", PG_JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "reconciled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("reconciliation_results", schema=SCHEMA)
    op.drop_table("pnl_snapshots", schema=SCHEMA)
    op.drop_table("nav_snapshots", schema=SCHEMA)
    op.drop_index("ix_finalized_prices_date", table_name="finalized_prices", schema=SCHEMA)
    op.drop_table("finalized_prices", schema=SCHEMA)
    op.drop_table("run_steps", schema=SCHEMA)
    op.drop_index("ix_eod_runs_fund", table_name="runs", schema=SCHEMA)
    op.drop_index("ix_eod_runs_date", table_name="runs", schema=SCHEMA)
    op.drop_table("runs", schema=SCHEMA)
