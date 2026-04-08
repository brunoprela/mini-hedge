"""Backtesting schema — backtest runs with config, results, and trades.

Revision ID: 001
Revises: None
Create Date: 2026-04-08
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

SCHEMA = "platform"


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("strategy_name", sa.String(128), nullable=False),
        sa.Column("config", PG_JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("results", PG_JSONB(), nullable=True),
        sa.Column("equity_curve", PG_JSONB(), nullable=True),
        sa.Column("trades", PG_JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_backtest_status",
        "backtest_runs",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_backtest_strategy",
        "backtest_runs",
        ["strategy_name"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_strategy",
        table_name="backtest_runs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_backtest_status",
        table_name="backtest_runs",
        schema=SCHEMA,
    )
    op.drop_table("backtest_runs", schema=SCHEMA)
