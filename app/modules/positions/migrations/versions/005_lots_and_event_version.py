"""Add lots read model table, event_version column, and created_at index.

- positions.lots: projected read model for FIFO cost basis tracking
- event_version on positions.events: schema evolution support
- ix_events_created index: time-range queries and archival

Revision ID: 005
Revises: 004
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_schema() -> str:
    """Resolve the target schema from Alembic config attributes."""
    from alembic import context as alembic_ctx

    schema = getattr(alembic_ctx.config.attributes, "target_schema", None)
    if schema is None:
        schema = alembic_ctx.config.attributes.get("target_schema", "positions")
    return schema


def upgrade() -> None:
    schema = _get_schema()

    # --- Lots read model table ---
    op.create_table(
        "lots",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("original_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_id", PG_UUID(as_uuid=False), nullable=False),
        sa.CheckConstraint("quantity != 0", name="valid_lot"),
        schema=schema,
    )
    op.create_index(
        "ix_pos_lots_position",
        "lots",
        ["portfolio_id", "instrument_id"],
        schema=schema,
    )

    # --- event_version column on events ---
    op.add_column(
        "events",
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        schema=schema,
    )

    # --- created_at index on events ---
    op.create_index(
        "ix_pos_events_created",
        "events",
        ["created_at"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _get_schema()
    op.drop_index("ix_pos_events_created", table_name="events", schema=schema)
    op.drop_column("events", "event_version", schema=schema)
    op.drop_index("ix_pos_lots_position", table_name="lots", schema=schema)
    op.drop_table("lots", schema=schema)
