"""Add hash chain columns to audit_log table.

Each audit log entry stores a SHA-256 hash of its content concatenated
with the previous entry's hash, forming a tamper-evident chain.

Revision ID: 009
Revises: 008
Create Date: 2026-04-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("prev_hash", sa.String(64), nullable=True),
        schema="platform",
    )
    op.add_column(
        "audit_log",
        sa.Column("entry_hash", sa.String(64), nullable=False, server_default=""),
        schema="platform",
    )
    op.create_index(
        "ix_platform_audit_log_entry_hash",
        "audit_log",
        ["entry_hash"],
        schema="platform",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_audit_log_entry_hash",
        table_name="audit_log",
        schema="platform",
    )
    op.drop_column("audit_log", "entry_hash", schema="platform")
    op.drop_column("audit_log", "prev_hash", schema="platform")
