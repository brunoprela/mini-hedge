"""Add fund_id column and Row-Level Security policies for tenant isolation.

Adds fund_id (UUID FK to platform.funds) to events and current_positions.
Backfills from platform.portfolios → platform.funds.
Enables RLS with FORCE so policies apply even to the table owner.

Revision ID: 002
Revises: 001
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def _is_per_fund_schema() -> bool:
    """Detect if running against a per-fund schema (not the shared 'positions' schema).

    Migrations 002 and 003 are transitional — they only apply to the shared
    'positions' schema.  Per-fund schemas start fresh from 001.
    """
    from alembic import context as alembic_ctx

    schema = getattr(alembic_ctx.config.attributes, "target_schema", None)
    if schema is None:
        schema = alembic_ctx.config.attributes.get("target_schema")
    return schema is not None and schema != "positions"


def upgrade() -> None:
    if _is_per_fund_schema():
        return

    # ------------------------------------------------------------------
    # 1. Add fund_id column (nullable initially for backfill)
    # ------------------------------------------------------------------
    op.add_column(
        "current_positions",
        sa.Column("fund_id", PG_UUID(), nullable=True),
        schema="positions",
    )
    op.add_column(
        "events",
        sa.Column("fund_id", PG_UUID(), nullable=True),
        schema="positions",
    )

    # ------------------------------------------------------------------
    # 2. Backfill fund_id from platform.portfolios → platform.funds
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE positions.current_positions cp
        SET fund_id = p.fund_id
        FROM platform.portfolios p
        WHERE cp.portfolio_id = p.id
        """
    )
    op.execute(
        """
        UPDATE positions.events e
        SET fund_id = p.fund_id
        FROM platform.portfolios p
        WHERE split_part(e.aggregate_id, ':', 1)::uuid = p.id
        """
    )

    # ------------------------------------------------------------------
    # 3. Make NOT NULL, add FK constraints and indexes
    # ------------------------------------------------------------------
    op.alter_column("current_positions", "fund_id", nullable=False, schema="positions")
    op.alter_column("events", "fund_id", nullable=False, schema="positions")

    op.create_foreign_key(
        "fk_current_positions_fund",
        "current_positions",
        "funds",
        ["fund_id"],
        ["id"],
        source_schema="positions",
        referent_schema="platform",
    )
    op.create_foreign_key(
        "fk_events_fund",
        "events",
        "funds",
        ["fund_id"],
        ["id"],
        source_schema="positions",
        referent_schema="platform",
    )

    op.create_index(
        "ix_pos_current_fund",
        "current_positions",
        ["fund_id"],
        schema="positions",
    )
    op.create_index(
        "ix_pos_events_fund",
        "events",
        ["fund_id"],
        schema="positions",
    )

    # ------------------------------------------------------------------
    # 4. Enable Row-Level Security with FORCE
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE positions.current_positions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE positions.current_positions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON positions.current_positions
            USING (
                current_setting('app.current_fund_id', true) = 'BYPASS'
                OR fund_id = current_setting('app.current_fund_id', true)::uuid
            )
        """
    )

    op.execute("ALTER TABLE positions.events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE positions.events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON positions.events
            USING (
                current_setting('app.current_fund_id', true) = 'BYPASS'
                OR fund_id = current_setting('app.current_fund_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    # Remove RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON positions.current_positions")
    op.execute("ALTER TABLE positions.current_positions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON positions.events")
    op.execute("ALTER TABLE positions.events DISABLE ROW LEVEL SECURITY")

    # Remove FK constraints and indexes
    op.drop_index("ix_pos_events_fund", table_name="events", schema="positions")
    op.drop_index("ix_pos_current_fund", table_name="current_positions", schema="positions")
    op.drop_constraint("fk_events_fund", "events", schema="positions", type_="foreignkey")
    op.drop_constraint(
        "fk_current_positions_fund",
        "current_positions",
        schema="positions",
        type_="foreignkey",
    )

    # Remove columns
    op.drop_column("events", "fund_id", schema="positions")
    op.drop_column("current_positions", "fund_id", schema="positions")
