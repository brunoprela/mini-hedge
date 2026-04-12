"""Add GIN index on audit_log.payload JSONB column.

Supports efficient queries filtering by entity_type, entity_id,
and correlation_id stored inside the payload JSON.

Revision ID: 016
Revises: 015
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "016"
down_revision: str = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"


def upgrade() -> None:
    op.create_index(
        "ix_platform_audit_log_payload_gin",
        "audit_log",
        ["payload"],
        schema=SCHEMA,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_platform_audit_log_actor_id",
        "audit_log",
        ["actor_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_audit_log_actor_id", table_name="audit_log", schema=SCHEMA)
    op.drop_index("ix_platform_audit_log_payload_gin", table_name="audit_log", schema=SCHEMA)
