"""Create audit_log table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=True),
        sa.Column("fund_slug", sa.String(64), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_audit_log_event_type", "audit_log", ["event_type"], schema="platform"
    )
    op.create_index(
        "ix_platform_audit_log_fund_slug", "audit_log", ["fund_slug"], schema="platform"
    )
    op.create_index(
        "ix_platform_audit_log_created_at", "audit_log", ["created_at"], schema="platform"
    )


def downgrade() -> None:
    op.drop_index("ix_platform_audit_log_created_at", table_name="audit_log", schema="platform")
    op.drop_index("ix_platform_audit_log_fund_slug", table_name="audit_log", schema="platform")
    op.drop_index("ix_platform_audit_log_event_type", table_name="audit_log", schema="platform")
    op.drop_table("audit_log", schema="platform")
