"""Position keeping schema — event store and read models.

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
PG_JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    # Schema creation is handled by env.py / fund_schema.py — not here.

    # Event store (append-only, source of truth)
    op.create_table(
        "events",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("aggregate_id", sa.String(128), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", PG_JSONB(), nullable=False),
        sa.Column(
            "metadata",
            PG_JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("aggregate_id", "sequence_number"),
        schema="positions",
    )
    op.create_index(
        "ix_pos_events_aggregate",
        "events",
        ["aggregate_id", "sequence_number"],
        schema="positions",
    )
    op.create_index(
        "ix_pos_events_type",
        "events",
        ["event_type"],
        schema="positions",
    )

    # Read model: current positions (denormalized for fast queries)
    op.create_table(
        "current_positions",
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "avg_cost",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "cost_basis",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "realized_pnl",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "market_price",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "market_value",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "unrealized_pnl",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("portfolio_id", "instrument_id"),
        schema="positions",
    )
    op.create_index(
        "ix_pos_current_portfolio",
        "current_positions",
        ["portfolio_id"],
        schema="positions",
    )


def downgrade() -> None:
    op.drop_table("current_positions", schema="positions")
    op.drop_table("events", schema="positions")
