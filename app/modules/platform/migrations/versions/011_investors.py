"""Investor registry — platform-scoped investor entities.

Investors can invest in multiple funds. Their per-fund capital accounts
live in fund-scoped schemas; this table holds the identity.

Revision ID: 011
Revises: 010
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "investors",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("tax_jurisdiction", sa.String(8), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_investors_entity_type",
        "investors",
        ["entity_type"],
        schema="platform",
    )
    op.create_index(
        "ix_platform_investors_active",
        "investors",
        ["is_active"],
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("investors", schema="platform")
