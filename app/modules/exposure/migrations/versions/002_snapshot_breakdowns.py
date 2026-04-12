"""Exposure snapshot breakdown sub-table — relational storage for per-dimension breakdowns.

Revision ID: 002
Revises: 001
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "exposure_snapshot_breakdowns",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column(
            "snapshot_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.exposure_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("long_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("short_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("gross_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("weight_pct", sa.Numeric(10, 6), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_exp_bd_snapshot",
        "exposure_snapshot_breakdowns",
        ["snapshot_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_exp_bd_dimension_key",
        "exposure_snapshot_breakdowns",
        ["dimension", "key"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exp_bd_dimension_key",
        table_name="exposure_snapshot_breakdowns",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_exp_bd_snapshot",
        table_name="exposure_snapshot_breakdowns",
        schema=SCHEMA,
    )
    op.drop_table("exposure_snapshot_breakdowns", schema=SCHEMA)
