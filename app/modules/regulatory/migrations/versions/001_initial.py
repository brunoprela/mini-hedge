"""Regulatory schema — filings, investor statements, performance letters.

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

SCHEMA = "positions"


def upgrade() -> None:
    # Regulatory filings
    op.create_table(
        "regulatory_filings",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("filing_type", sa.String(32), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("data", PG_JSONB(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_reg_filing_type",
        "regulatory_filings",
        ["filing_type"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_reg_filing_period",
        "regulatory_filings",
        ["reporting_period"],
        schema=SCHEMA,
    )

    # Investor statements
    op.create_table(
        "investor_statements",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("investor_id", PG_UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("statement_type", sa.String(32), nullable=False),
        sa.Column("data", PG_JSONB(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_inv_stmt_investor",
        "investor_statements",
        ["investor_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_inv_stmt_period",
        "investor_statements",
        ["period_end"],
        schema=SCHEMA,
    )

    # Performance letters
    op.create_table(
        "performance_letters",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("data", PG_JSONB(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_perf_letter_period",
        "performance_letters",
        ["period"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_perf_letter_period",
        table_name="performance_letters",
        schema=SCHEMA,
    )
    op.drop_table("performance_letters", schema=SCHEMA)
    op.drop_index(
        "ix_inv_stmt_period",
        table_name="investor_statements",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_inv_stmt_investor",
        table_name="investor_statements",
        schema=SCHEMA,
    )
    op.drop_table("investor_statements", schema=SCHEMA)
    op.drop_index(
        "ix_reg_filing_period",
        table_name="regulatory_filings",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_reg_filing_type",
        table_name="regulatory_filings",
        schema=SCHEMA,
    )
    op.drop_table("regulatory_filings", schema=SCHEMA)
