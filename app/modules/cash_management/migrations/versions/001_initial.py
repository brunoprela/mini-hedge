"""Cash management schema — balances, journal, settlements, flows, projections.

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
    # Cash balances
    op.create_table(
        "cash_balances",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "available_balance",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "pending_inflows",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "pending_outflows",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cash_bal_portfolio",
        "cash_balances",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cash_bal_portfolio_ccy",
        "cash_balances",
        ["portfolio_id", "currency"],
        unique=True,
        schema=SCHEMA,
    )

    # Cash journal (double-entry audit trail)
    op.create_table(
        "cash_balance_journal",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("entry_type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=False),
        sa.Column("flow_type", sa.String(30), nullable=False),
        sa.Column("reference_id", sa.String(50), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cash_journal_portfolio",
        "cash_balance_journal",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cash_journal_time",
        "cash_balance_journal",
        ["created_at"],
        schema=SCHEMA,
    )

    # Cash settlements
    op.create_table(
        "cash_settlements",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("order_id", PG_UUID(), nullable=True),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("settlement_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
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
        "ix_settle_portfolio",
        "cash_settlements",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_settle_date",
        "cash_settlements",
        ["settlement_date"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_settle_status",
        "cash_settlements",
        ["status"],
        schema=SCHEMA,
    )

    # Scheduled flows
    op.create_table(
        "cash_scheduled_flows",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("flow_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sched_portfolio",
        "cash_scheduled_flows",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sched_date",
        "cash_scheduled_flows",
        ["flow_date"],
        schema=SCHEMA,
    )

    # Cash projections
    op.create_table(
        "cash_projections",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column(
            "entries",
            PG_JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_proj_portfolio",
        "cash_projections",
        ["portfolio_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_proj_time",
        "cash_projections",
        ["projected_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_proj_time", table_name="cash_projections", schema=SCHEMA)
    op.drop_index("ix_proj_portfolio", table_name="cash_projections", schema=SCHEMA)
    op.drop_table("cash_projections", schema=SCHEMA)
    op.drop_index("ix_sched_date", table_name="cash_scheduled_flows", schema=SCHEMA)
    op.drop_index(
        "ix_sched_portfolio",
        table_name="cash_scheduled_flows",
        schema=SCHEMA,
    )
    op.drop_table("cash_scheduled_flows", schema=SCHEMA)
    op.drop_index("ix_settle_status", table_name="cash_settlements", schema=SCHEMA)
    op.drop_index("ix_settle_date", table_name="cash_settlements", schema=SCHEMA)
    op.drop_index("ix_settle_portfolio", table_name="cash_settlements", schema=SCHEMA)
    op.drop_table("cash_settlements", schema=SCHEMA)
    op.drop_index(
        "ix_cash_journal_time",
        table_name="cash_balance_journal",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_cash_journal_portfolio",
        table_name="cash_balance_journal",
        schema=SCHEMA,
    )
    op.drop_table("cash_balance_journal", schema=SCHEMA)
    op.drop_index(
        "ix_cash_bal_portfolio_ccy",
        table_name="cash_balances",
        schema=SCHEMA,
    )
    op.drop_index("ix_cash_bal_portfolio", table_name="cash_balances", schema=SCHEMA)
    op.drop_table("cash_balances", schema=SCHEMA)
