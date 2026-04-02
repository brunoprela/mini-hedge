"""Add fund_slug to events and current_positions for tenant isolation.

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


def upgrade() -> None:
    # Add fund_slug to events table
    op.add_column(
        "events",
        sa.Column("fund_slug", sa.String(64), nullable=True),
        schema="positions",
    )
    # Backfill existing events via the portfolio's fund slug.
    # aggregate_id format is "{portfolio_id}:{instrument_id}".
    op.execute(
        """
        UPDATE positions.events e
        SET fund_slug = f.slug
        FROM platform.portfolios p
        JOIN platform.funds f ON f.id = p.fund_id
        WHERE SPLIT_PART(e.aggregate_id, ':', 1)::uuid = p.id
          AND e.fund_slug IS NULL
        """
    )
    # Default any remaining (shouldn't happen) to 'fund-alpha'
    op.execute(
        """
        UPDATE positions.events
        SET fund_slug = 'fund-alpha'
        WHERE fund_slug IS NULL
        """
    )
    op.alter_column("events", "fund_slug", nullable=False, schema="positions")
    op.create_index(
        "ix_pos_events_fund",
        "events",
        ["fund_slug"],
        schema="positions",
    )

    # Add fund_slug to current_positions table
    op.add_column(
        "current_positions",
        sa.Column("fund_slug", sa.String(64), nullable=True),
        schema="positions",
    )
    # Backfill from platform.portfolios → platform.funds
    op.execute(
        """
        UPDATE positions.current_positions cp
        SET fund_slug = f.slug
        FROM platform.portfolios p
        JOIN platform.funds f ON f.id = p.fund_id
        WHERE cp.portfolio_id::uuid = p.id
          AND cp.fund_slug IS NULL
        """
    )
    op.execute(
        """
        UPDATE positions.current_positions
        SET fund_slug = 'fund-alpha'
        WHERE fund_slug IS NULL
        """
    )
    op.alter_column("current_positions", "fund_slug", nullable=False, schema="positions")
    op.create_index(
        "ix_pos_current_fund",
        "current_positions",
        ["fund_slug"],
        schema="positions",
    )


def downgrade() -> None:
    op.drop_index("ix_pos_current_fund", table_name="current_positions", schema="positions")
    op.drop_column("current_positions", "fund_slug", schema="positions")
    op.drop_index("ix_pos_events_fund", table_name="events", schema="positions")
    op.drop_column("events", "fund_slug", schema="positions")
