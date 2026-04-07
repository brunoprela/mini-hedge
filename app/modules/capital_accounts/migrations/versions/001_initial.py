"""Capital accounts and transactions schema.

Revision ID: 001
Revises: None
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

# Tables live in the "positions" logical schema, which schema_translate_map
# rewrites to the active fund schema (e.g. fund_alpha) at runtime.
SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "capital_accounts",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("investor_id", PG_UUID(), nullable=False),
        sa.Column("share_class", sa.String(32), nullable=False, server_default="default"),
        sa.Column("beginning_capital", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("contributions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("withdrawals", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("pnl_allocation", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column(
            "management_fee_allocation", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "performance_fee_allocation", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column("ending_capital", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("ownership_pct", sa.Numeric(8, 6), nullable=False, server_default="0"),
        sa.Column("shares_held", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ca_investor_date",
        "capital_accounts",
        ["investor_id", "effective_date"],
        schema=SCHEMA,
    )
    op.create_index("ix_ca_effective_date", "capital_accounts", ["effective_date"], schema=SCHEMA)
    op.create_index("ix_ca_share_class", "capital_accounts", ["share_class"], schema=SCHEMA)

    op.create_table(
        "capital_transactions",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("capital_account_id", PG_UUID(), nullable=False),
        sa.Column("investor_id", PG_UUID(), nullable=False),
        sa.Column("transaction_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("nav_per_share", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_ct_account", "capital_transactions", ["capital_account_id"], schema=SCHEMA)
    op.create_index("ix_ct_type", "capital_transactions", ["transaction_type"], schema=SCHEMA)
    op.create_index("ix_ct_date", "capital_transactions", ["business_date"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_ct_date", table_name="capital_transactions", schema=SCHEMA)
    op.drop_index("ix_ct_type", table_name="capital_transactions", schema=SCHEMA)
    op.drop_index("ix_ct_account", table_name="capital_transactions", schema=SCHEMA)
    op.drop_table("capital_transactions", schema=SCHEMA)
    op.drop_index("ix_ca_share_class", table_name="capital_accounts", schema=SCHEMA)
    op.drop_index("ix_ca_effective_date", table_name="capital_accounts", schema=SCHEMA)
    op.drop_index("ix_ca_investor_date", table_name="capital_accounts", schema=SCHEMA)
    op.drop_table("capital_accounts", schema=SCHEMA)
