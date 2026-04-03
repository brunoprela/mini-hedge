"""Exposure snapshots schema.

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

# Tables live in the "positions" logical schema, which schema_translate_map
# rewrites to the active fund schema (e.g. fund_alpha) at runtime.
SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "exposure_snapshots",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("gross_exposure", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_exposure", sa.Numeric(18, 4), nullable=False),
        sa.Column("long_exposure", sa.Numeric(18, 4), nullable=False),
        sa.Column("short_exposure", sa.Numeric(18, 4), nullable=False),
        sa.Column("long_count", sa.Integer(), nullable=False),
        sa.Column("short_count", sa.Integer(), nullable=False),
        sa.Column("breakdowns", PG_JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_exp_snapshot_portfolio", "exposure_snapshots", ["portfolio_id"], schema=SCHEMA
    )
    op.create_index("ix_exp_snapshot_time", "exposure_snapshots", ["snapshot_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_exp_snapshot_time", table_name="exposure_snapshots", schema=SCHEMA)
    op.drop_index("ix_exp_snapshot_portfolio", table_name="exposure_snapshots", schema=SCHEMA)
    op.drop_table("exposure_snapshots", schema=SCHEMA)
