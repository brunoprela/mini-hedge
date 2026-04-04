"""Add annual_drift, annual_volatility, spread_bps to instruments.

These parameters are fetched from the mock-exchange reference data API
and used by risk_engine, attribution, and alpha_engine for synthetic
returns generation.

Revision ID: 002
Revises: 001
Create Date: 2026-04-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("annual_drift", sa.Float(), nullable=True),
        schema="security_master",
    )
    op.add_column(
        "instruments",
        sa.Column("annual_volatility", sa.Float(), nullable=True),
        schema="security_master",
    )
    op.add_column(
        "instruments",
        sa.Column("spread_bps", sa.Float(), nullable=True),
        schema="security_master",
    )


def downgrade() -> None:
    op.drop_column("instruments", "spread_bps", schema="security_master")
    op.drop_column("instruments", "annual_volatility", schema="security_master")
    op.drop_column("instruments", "annual_drift", schema="security_master")
