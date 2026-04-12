"""Add instrument_identifiers table for multi-ID lookup (ISIN, CUSIP, SEDOL, etc.).

Revision ID: 003
Revises: 002
Create Date: 2026-04-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "security_master"


def upgrade() -> None:
    op.create_table(
        "instrument_identifiers",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "instrument_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey(f"{SCHEMA}.instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("id_type", sa.String(32), nullable=False),
        sa.Column("id_value", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("id_type", "id_value", name="uq_identifier_type_value"),
        sa.Index("ix_sm_identifiers_instrument", "instrument_id"),
        sa.Index("ix_sm_identifiers_type_value", "id_type", "id_value"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("instrument_identifiers", schema=SCHEMA)
