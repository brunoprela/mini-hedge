"""Add instrument_id index to current_positions for MTM lookups.

Revision ID: 004
Revises: 003
Create Date: 2026-04-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_pos_current_instrument",
        "current_positions",
        ["instrument_id"],
        schema="positions",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pos_current_instrument",
        table_name="current_positions",
        schema="positions",
    )
