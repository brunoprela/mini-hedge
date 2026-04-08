"""Investor KYC/AML screening status table.

Revision ID: 012
Revises: 011
Create Date: 2026-04-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "platform"


def upgrade() -> None:
    op.create_table(
        "investor_kyc",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column(
            "investor_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.investors.id"),
            nullable=False,
        ),
        sa.Column(
            "kyc_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "aml_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("sanctions_clear", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pep_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "source_of_funds_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "accredited_investor",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("last_screened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("screening_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("screening_provider", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_investor_kyc_investor",
        "investor_kyc",
        ["investor_id"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("investor_kyc", schema=SCHEMA)
