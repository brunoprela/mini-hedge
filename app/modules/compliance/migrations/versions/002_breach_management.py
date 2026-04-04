"""Add breach management fields — breach_type, grace periods, auto-resolution.

Revision ID: 002
Revises: 001
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Logical schema name used in ORM models.  At runtime the env.py's
# schema_translate_map remaps this to the real fund schema (fund_alpha,
# etc.).  However, Alembic's add_column / create_index emit literal SQL
# that bypasses schema_translate_map, so we resolve the *actual* target
# schema at migration time instead.
_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA)


def upgrade() -> None:
    schema = _schema()

    # --- compliance_violations: breach management columns ---
    op.add_column(
        "compliance_violations",
        sa.Column(
            "breach_type",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
        schema=schema,
    )
    op.add_column(
        "compliance_violations",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.add_column(
        "compliance_violations",
        sa.Column("resolution_type", sa.String(16), nullable=True),
        schema=schema,
    )

    # --- compliance_rules: grace period ---
    op.add_column(
        "compliance_rules",
        sa.Column(
            "grace_period_hours",
            sa.Integer(),
            nullable=True,
        ),
        schema=schema,
    )

    # Index on active violations with deadlines for efficient breach monitoring
    op.create_index(
        "ix_comp_viol_active_deadline",
        "compliance_violations",
        ["resolved_at", "deadline_at"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_index(
        "ix_comp_viol_active_deadline",
        table_name="compliance_violations",
        schema=schema,
    )
    op.drop_column("compliance_rules", "grace_period_hours", schema=schema)
    op.drop_column("compliance_violations", "resolution_type", schema=schema)
    op.drop_column("compliance_violations", "deadline_at", schema=schema)
    op.drop_column("compliance_violations", "breach_type", schema=schema)
