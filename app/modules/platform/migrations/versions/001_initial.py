"""Platform schema — fund registry and portfolio management.

Revision ID: 001
Revises: None
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")

    op.create_table(
        "funds",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "base_currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "offboarded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_funds_slug",
        "funds",
        ["slug"],
        schema="platform",
    )
    op.create_index(
        "ix_platform_funds_status",
        "funds",
        ["status"],
        schema="platform",
    )

    op.create_table(
        "portfolios",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "fund_id",
            PG_UUID(),
            sa.ForeignKey("platform.funds.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("strategy", sa.String(128), nullable=True),
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
        sa.UniqueConstraint("fund_id", "slug"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_portfolios_fund",
        "portfolios",
        ["fund_id"],
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("portfolios", schema="platform")
    op.drop_table("funds", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform")
