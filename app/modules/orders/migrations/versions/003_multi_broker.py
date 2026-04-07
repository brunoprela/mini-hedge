"""Add multi-broker routing support.

Adds broker_id to orders and order_fills, plus tables for broker scorecards,
routing rules, and routing decisions (audit trail for best execution).

Revision ID: 003
Revises: 002
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB

_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return str(stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA))


def upgrade() -> None:
    schema = _schema()

    # --- broker_id on orders ---
    op.add_column(
        "orders",
        sa.Column("broker_id", sa.String(64), nullable=True),
        schema=schema,
    )

    # --- broker_id on order_fills ---
    op.add_column(
        "order_fills",
        sa.Column("broker_id", sa.String(64), nullable=True),
        schema=schema,
    )

    # --- Broker scorecards ---
    op.create_table(
        "broker_scorecards",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("broker_id", sa.String(64), nullable=False),
        sa.Column("instrument_class", sa.String(32), nullable=True),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_fills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rejects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_slippage_bps", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("avg_fill_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_cost_bps", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("fill_rate", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=schema,
    )
    op.create_index(
        "ix_broker_scorecards_broker_id",
        "broker_scorecards",
        ["broker_id"],
        schema=schema,
    )

    # --- Routing rules ---
    op.create_table(
        "routing_rules",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=True),
        sa.Column("instrument_class", sa.String(32), nullable=True),
        sa.Column("min_size", sa.Numeric(18, 8), nullable=True),
        sa.Column("max_size", sa.Numeric(18, 8), nullable=True),
        sa.Column("preferred_broker_id", sa.String(64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
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
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=schema,
    )
    op.create_index(
        "ix_routing_rules_fund",
        "routing_rules",
        ["fund_slug"],
        schema=schema,
    )

    # --- Routing decisions (best execution audit trail) ---
    op.create_table(
        "routing_decisions",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("order_id", PG_UUID(), nullable=False),
        sa.Column("broker_id", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("score_breakdown", PG_JSONB(), nullable=True),
        sa.Column("rule_ids_matched", PG_JSONB(), nullable=True),
        sa.Column("decision_reason", sa.String(512), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=schema,
    )
    op.create_index(
        "ix_routing_decisions_order_id",
        "routing_decisions",
        ["order_id"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    op.drop_index("ix_routing_decisions_order_id", table_name="routing_decisions", schema=schema)
    op.drop_table("routing_decisions", schema=schema)
    op.drop_index("ix_routing_rules_fund", table_name="routing_rules", schema=schema)
    op.drop_table("routing_rules", schema=schema)
    op.drop_index("ix_broker_scorecards_broker_id", table_name="broker_scorecards", schema=schema)
    op.drop_table("broker_scorecards", schema=schema)
    op.drop_column("order_fills", "broker_id", schema=schema)
    op.drop_column("orders", "broker_id", schema=schema)
