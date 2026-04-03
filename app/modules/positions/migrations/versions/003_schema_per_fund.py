"""Migrate from shared positions schema + RLS to per-fund schemas.

For each active fund, creates a ``fund_{slug}`` schema, copies the fund's
position data into it, then removes RLS policies and the shared data.

Revision ID: 003
Revises: 002
Create Date: 2026-04-02
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


def _is_per_fund_schema() -> bool:
    """Skip this migration for per-fund schemas — it only applies to the shared schema."""
    from alembic import context as alembic_ctx

    schema = getattr(alembic_ctx.config.attributes, "target_schema", None)
    if schema is None:
        schema = alembic_ctx.config.attributes.get("target_schema")
    return schema is not None and schema != "positions"


def upgrade() -> None:
    if _is_per_fund_schema():
        return

    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Discover all active funds
    # ------------------------------------------------------------------
    funds = conn.execute(
        sa.text("SELECT id, slug FROM platform.funds WHERE status = 'active'")
    ).fetchall()

    for fund_id, fund_slug in funds:
        schema = f"fund_{fund_slug.replace('-', '_')}"

        # --------------------------------------------------------------
        # 2. Create per-fund schema
        # --------------------------------------------------------------
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        # --------------------------------------------------------------
        # 3. Create tables in the fund schema (mirrors 001_initial)
        # --------------------------------------------------------------
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
            schema=schema,
        )
        op.create_index(
            f"ix_{fund_slug}_events_aggregate",
            "events",
            ["aggregate_id", "sequence_number"],
            schema=schema,
        )
        op.create_index(f"ix_{fund_slug}_events_type", "events", ["event_type"], schema=schema)

        op.create_table(
            "current_positions",
            sa.Column("portfolio_id", PG_UUID(), nullable=False),
            sa.Column("instrument_id", sa.String(32), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("avg_cost", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("cost_basis", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("market_price", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("market_value", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column(
                "last_updated",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("portfolio_id", "instrument_id"),
            schema=schema,
        )
        op.create_index(
            f"ix_{fund_slug}_current_portfolio",
            "current_positions",
            ["portfolio_id"],
            schema=schema,
        )

        # --------------------------------------------------------------
        # 4. Copy data for this fund from shared schema
        # --------------------------------------------------------------
        op.execute(
            f"""
            INSERT INTO {schema}.events
                (id, aggregate_id, sequence_number, event_type,
                 event_data, metadata, created_at)
            SELECT id, aggregate_id, sequence_number, event_type,
                   event_data, metadata, created_at
            FROM positions.events
            WHERE fund_id = '{fund_id}'
            """
        )
        op.execute(
            f"""
            INSERT INTO {schema}.current_positions
                (portfolio_id, instrument_id, quantity, avg_cost, cost_basis,
                 realized_pnl, market_price, market_value, unrealized_pnl,
                 currency, last_updated)
            SELECT portfolio_id, instrument_id, quantity, avg_cost, cost_basis,
                   realized_pnl, market_price, market_value, unrealized_pnl,
                   currency, last_updated
            FROM positions.current_positions
            WHERE fund_id = '{fund_id}'
            """
        )

    # ------------------------------------------------------------------
    # 5. Drop RLS policies from shared schema
    # ------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON positions.current_positions")
    op.execute("ALTER TABLE positions.current_positions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON positions.events")
    op.execute("ALTER TABLE positions.events DISABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # 6. Drop shared position data (now lives in per-fund schemas)
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS positions.ix_pos_events_fund")
    op.execute("DROP INDEX IF EXISTS positions.ix_pos_current_fund")
    op.drop_constraint(
        "fk_events_fund",
        "events",
        schema="positions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_current_positions_fund",
        "current_positions",
        schema="positions",
        type_="foreignkey",
    )
    op.drop_column("events", "fund_id", schema="positions")
    op.drop_column("current_positions", "fund_id", schema="positions")

    # Drop shared tables entirely (data is in per-fund schemas now)
    op.drop_table("events", schema="positions")
    op.drop_table("current_positions", schema="positions")


def downgrade() -> None:
    # Downgrade is destructive — per-fund schemas must be dropped manually.
    # Re-add fund_id columns and RLS policies to restore the shared schema.
    raise NotImplementedError(
        "Downgrade from schema-per-fund to shared schema is not supported. "
        "Restore from backup if needed."
    )
