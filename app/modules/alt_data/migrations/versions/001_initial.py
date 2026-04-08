"""Alternative data schema — feeds and data points.

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
PG_JSONB = sa.dialects.postgresql.JSONB

SCHEMA = "platform"


def upgrade() -> None:
    # Alt data feeds
    op.create_table(
        "alt_data_feeds",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "instruments",
            PG_JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("quality", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config", PG_JSONB(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_altfeed_source_active",
        "alt_data_feeds",
        ["source", "is_active"],
        schema=SCHEMA,
    )

    # Alt data points
    op.create_table(
        "alt_data_points",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "feed_id",
            PG_UUID(),
            sa.ForeignKey("platform.alt_data_feeds.id"),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.String(32), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("value", sa.Numeric(18, 8), nullable=False),
        sa.Column("metadata", PG_JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_altpt_feed_ts",
        "alt_data_points",
        ["feed_id", "timestamp"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_altpt_instrument_ts",
        "alt_data_points",
        ["instrument_id", "timestamp"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_altpt_instrument_ts",
        table_name="alt_data_points",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_altpt_feed_ts",
        table_name="alt_data_points",
        schema=SCHEMA,
    )
    op.drop_table("alt_data_points", schema=SCHEMA)
    op.drop_index(
        "ix_altfeed_source_active",
        table_name="alt_data_feeds",
        schema=SCHEMA,
    )
    op.drop_table("alt_data_feeds", schema=SCHEMA)
