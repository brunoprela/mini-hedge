"""Fund structures schema — master-feeder links, strategy books, FoF holdings.

Revision ID: 001
Revises: None
Create Date: 2026-04-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

SCHEMA = "positions"


def upgrade() -> None:
    # Master-feeder links
    op.create_table(
        "master_feeder_links",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("master_fund_slug", sa.String(64), nullable=False),
        sa.Column(
            "feeder_fund_slug",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
        sa.Column("allocation_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_mf_master_slug",
        "master_feeder_links",
        ["master_fund_slug"],
        schema=SCHEMA,
    )

    # Strategy books
    op.create_table(
        "strategy_books",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column(
            "parent_id",
            PG_UUID(),
            sa.ForeignKey("positions.strategy_books.id"),
            nullable=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=True),
        sa.Column(
            "target_allocation_pct",
            sa.Numeric(8, 6),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sb_fund_slug",
        "strategy_books",
        ["fund_slug"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sb_parent_id",
        "strategy_books",
        ["parent_id"],
        schema=SCHEMA,
    )

    # Fund-of-funds holdings
    op.create_table(
        "fof_holdings",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fof_fund_slug", sa.String(64), nullable=False),
        sa.Column("underlying_fund_slug", sa.String(64), nullable=True),
        sa.Column("underlying_fund_name", sa.String(128), nullable=False),
        sa.Column("allocation_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column(
            "current_nav",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        "ix_fof_slug",
        "fof_holdings",
        ["fof_fund_slug"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fof_slug",
        table_name="fof_holdings",
        schema=SCHEMA,
    )
    op.drop_table("fof_holdings", schema=SCHEMA)
    op.drop_index(
        "ix_sb_parent_id",
        table_name="strategy_books",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_sb_fund_slug",
        table_name="strategy_books",
        schema=SCHEMA,
    )
    op.drop_table("strategy_books", schema=SCHEMA)
    op.drop_index(
        "ix_mf_master_slug",
        table_name="master_feeder_links",
        schema=SCHEMA,
    )
    op.drop_table("master_feeder_links", schema=SCHEMA)
