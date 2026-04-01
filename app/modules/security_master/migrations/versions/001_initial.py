"""Security master schema — instruments and equity extensions.

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
    op.execute("CREATE SCHEMA IF NOT EXISTS security_master")

    op.create_table(
        "instruments",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "ticker",
            sa.String(32),
            nullable=False,
            unique=True,
        ),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("industry", sa.String(128), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("listed_date", sa.Date(), nullable=True),
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
        schema="security_master",
    )
    op.create_index(
        "ix_sm_instruments_ticker",
        "instruments",
        ["ticker"],
        unique=True,
        schema="security_master",
    )
    op.create_index(
        "ix_sm_instruments_asset_class",
        "instruments",
        ["asset_class"],
        schema="security_master",
    )
    op.create_index(
        "ix_sm_instruments_active",
        "instruments",
        ["is_active"],
        schema="security_master",
    )

    op.create_table(
        "equity_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey("security_master.instruments.id"),
            primary_key=True,
        ),
        sa.Column(
            "shares_outstanding",
            sa.Numeric(18, 0),
            nullable=True,
        ),
        sa.Column(
            "dividend_yield",
            sa.Numeric(8, 6),
            nullable=True,
        ),
        sa.Column("market_cap", sa.Numeric(18, 2), nullable=True),
        sa.Column("free_float_pct", sa.Numeric(5, 2), nullable=True),
        schema="security_master",
    )


def downgrade() -> None:
    op.drop_table("equity_extensions", schema="security_master")
    op.drop_table("instruments", schema="security_master")
    op.execute("DROP SCHEMA IF EXISTS security_master")
