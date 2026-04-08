"""Reconciliation breaks table — first-class break tracking with resolution lifecycle.

Revision ID: 002
Revises: 001
Create Date: 2026-04-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB

SCHEMA = "eod"


def upgrade() -> None:
    op.create_table(
        "reconciliation_breaks",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=True),
        sa.Column("break_type", sa.String(32), nullable=False),
        sa.Column("internal_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("broker_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("admin_quantity", sa.Numeric(18, 8), nullable=True),
        sa.Column("difference", sa.Numeric(18, 8), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        # Cash break fields (null for position breaks)
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("internal_balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("admin_balance", sa.Numeric(18, 2), nullable=True),
        # Resolution lifecycle
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recon_breaks_portfolio_date",
        "reconciliation_breaks",
        ["portfolio_id", "business_date"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recon_breaks_status",
        "reconciliation_breaks",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recon_breaks_status",
        table_name="reconciliation_breaks",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_recon_breaks_portfolio_date",
        table_name="reconciliation_breaks",
        schema=SCHEMA,
    )
    op.drop_table("reconciliation_breaks", schema=SCHEMA)
