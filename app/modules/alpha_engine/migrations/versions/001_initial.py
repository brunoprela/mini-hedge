"""Alpha engine schema — scenarios, optimizations, weights, order intents.

Revision ID: 001
Revises: None
Create Date: 2026-04-03
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

SCHEMA = "positions"


def upgrade() -> None:
    # Scenario runs
    op.create_table(
        "alpha_scenario_runs",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("scenario_name", sa.String(100), nullable=False),
        sa.Column("trades", PG_JSONB(), nullable=False),
        sa.Column("result_summary", PG_JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_scenario_portfolio", "alpha_scenario_runs", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_scenario_time", "alpha_scenario_runs", ["created_at"], schema=SCHEMA)

    # Optimization runs
    op.create_table(
        "alpha_optimization_runs",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("objective", sa.String(30), nullable=False),
        sa.Column("expected_return", sa.Numeric(10, 6), nullable=False),
        sa.Column("expected_risk", sa.Numeric(10, 6), nullable=False),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_opt_portfolio", "alpha_optimization_runs", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_opt_time", "alpha_optimization_runs", ["created_at"], schema=SCHEMA)

    # Optimization weights
    op.create_table(
        "alpha_optimization_weights",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("optimization_run_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(20), nullable=False),
        sa.Column("current_weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("target_weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("delta_weight", sa.Numeric(10, 6), nullable=False),
        sa.Column("delta_shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("delta_value", sa.Numeric(18, 4), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opt_weight_run",
        "alpha_optimization_weights",
        ["optimization_run_id"],
        schema=SCHEMA,
    )

    # Order intents
    op.create_table(
        "alpha_order_intents",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("optimization_run_id", PG_UUID(), nullable=False),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(20), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_intent_run",
        "alpha_order_intents",
        ["optimization_run_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_intent_status",
        "alpha_order_intents",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_intent_status", table_name="alpha_order_intents", schema=SCHEMA)
    op.drop_index("ix_intent_run", table_name="alpha_order_intents", schema=SCHEMA)
    op.drop_table("alpha_order_intents", schema=SCHEMA)
    op.drop_index("ix_opt_weight_run", table_name="alpha_optimization_weights", schema=SCHEMA)
    op.drop_table("alpha_optimization_weights", schema=SCHEMA)
    op.drop_index("ix_opt_time", table_name="alpha_optimization_runs", schema=SCHEMA)
    op.drop_index("ix_opt_portfolio", table_name="alpha_optimization_runs", schema=SCHEMA)
    op.drop_table("alpha_optimization_runs", schema=SCHEMA)
    op.drop_index("ix_scenario_time", table_name="alpha_scenario_runs", schema=SCHEMA)
    op.drop_index("ix_scenario_portfolio", table_name="alpha_scenario_runs", schema=SCHEMA)
    op.drop_table("alpha_scenario_runs", schema=SCHEMA)
