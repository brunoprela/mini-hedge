"""Add fund_slug column to ai_analysis_results and research_notes for tenant isolation.

Revision ID: 002
Revises: 001
Create Date: 2026-04-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"


def upgrade() -> None:
    # Add fund_slug to ai_analysis_results
    op.add_column(
        "ai_analysis_results",
        sa.Column("fund_slug", sa.String(64), nullable=False, server_default="__backfill__"),
        schema=SCHEMA,
    )
    # Remove the server_default after column is added (it was only for existing rows)
    op.alter_column(
        "ai_analysis_results",
        "fund_slug",
        server_default=None,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_analysis_results_fund_slug",
        "ai_analysis_results",
        ["fund_slug"],
        schema=SCHEMA,
    )

    # Add fund_slug to research_notes
    op.add_column(
        "research_notes",
        sa.Column("fund_slug", sa.String(64), nullable=False, server_default="__backfill__"),
        schema=SCHEMA,
    )
    op.alter_column(
        "research_notes",
        "fund_slug",
        server_default=None,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_research_notes_fund_slug",
        "research_notes",
        ["fund_slug"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_notes_fund_slug",
        table_name="research_notes",
        schema=SCHEMA,
    )
    op.drop_column("research_notes", "fund_slug", schema=SCHEMA)
    op.drop_index(
        "ix_ai_analysis_results_fund_slug",
        table_name="ai_analysis_results",
        schema=SCHEMA,
    )
    op.drop_column("ai_analysis_results", "fund_slug", schema=SCHEMA)
