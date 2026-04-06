"""Archival index — tracks which months have been exported to cold storage.

Revision ID: 010
Revises: 009
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "archival_index",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("records_archived", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_archival_fund_period",
        "archival_index",
        ["fund_slug", "year", "month"],
        unique=True,
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("archival_index", schema="platform")
