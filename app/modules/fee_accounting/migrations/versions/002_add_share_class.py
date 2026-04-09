"""Add share_class column to fee_schedules and fee_accruals.

Revision ID: 002
Revises: 001
Create Date: 2026-04-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema_translate_map remaps "positions" to the real fund schema (fund_alpha,
# etc.).  However, Alembic's add_column / drop_index / create_index emit
# literal SQL that bypasses schema_translate_map, so we resolve the *actual*
# target schema at migration time instead.
_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return str(stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA))


def upgrade() -> None:
    schema = _schema()

    # Add share_class to fee_schedules
    op.add_column(
        "fee_schedules",
        sa.Column("share_class", sa.String(32), nullable=False, server_default="default"),
        schema=schema,
    )
    # Drop the old unique index on fund_slug only
    op.drop_index("ix_fee_schedules_fund_slug", table_name="fee_schedules", schema=schema)
    # Also drop the unique constraint that was auto-created by `unique=True` on the column
    op.drop_constraint("fee_schedules_fund_slug_key", "fee_schedules", schema=schema)
    # Create composite unique index on (fund_slug, share_class)
    op.create_index(
        "ix_fee_schedules_fund_class",
        "fee_schedules",
        ["fund_slug", "share_class"],
        unique=True,
        schema=schema,
    )

    # Add share_class to fee_accruals
    op.add_column(
        "fee_accruals",
        sa.Column("share_class", sa.String(32), nullable=False, server_default="default"),
        schema=schema,
    )

    # Add share_class to high_water_marks
    op.add_column(
        "high_water_marks",
        sa.Column("share_class", sa.String(32), nullable=False, server_default="default"),
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    op.drop_column("high_water_marks", "share_class", schema=schema)
    op.drop_column("fee_accruals", "share_class", schema=schema)
    op.drop_index("ix_fee_schedules_fund_class", table_name="fee_schedules", schema=schema)
    op.create_index(
        "ix_fee_schedules_fund_slug",
        "fee_schedules",
        ["fund_slug"],
        unique=True,
        schema=schema,
    )
    op.drop_column("fee_schedules", "share_class", schema=schema)
