"""Add restricted_instruments table.

Moves the restricted instrument list from inline JSON parameters on
compliance rules to a dedicated per-fund table, enabling shared lists
across rules and CRUD management.

Revision ID: 003
Revises: 002
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return str(stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA))


def upgrade() -> None:
    schema = _schema()
    op.create_table(
        "restricted_instruments",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(256), nullable=True),
        sa.Column("added_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "fund_slug", "instrument_id", name="uq_restricted_fund_instrument"
        ),
        schema=schema,
    )
    op.create_index(
        "ix_restricted_fund_slug",
        "restricted_instruments",
        ["fund_slug"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_table("restricted_instruments", schema=schema)
