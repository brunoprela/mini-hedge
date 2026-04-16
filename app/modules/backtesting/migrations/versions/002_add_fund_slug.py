"""Add fund_slug column to backtest_runs for tenant isolation.

Revision ID: 002
Revises: 001
Create Date: 2026-04-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column("fund_slug", sa.String(64), nullable=False, server_default="__backfill__"),
        schema=SCHEMA,
    )
    op.alter_column(
        "backtest_runs",
        "fund_slug",
        server_default=None,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_backtest_runs_fund_slug",
        "backtest_runs",
        ["fund_slug"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_runs_fund_slug",
        table_name="backtest_runs",
        schema=SCHEMA,
    )
    op.drop_column("backtest_runs", "fund_slug", schema=SCHEMA)
