"""FX hedging schema — forwards, interest rates.

Revision ID: 001
Revises: None
Create Date: 2026-04-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID

SCHEMA = "positions"


def upgrade() -> None:
    # FX forward contracts
    op.create_table(
        "fx_forwards",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("notional", sa.Numeric(18, 4), nullable=False),
        sa.Column("contract_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("spot_at_inception", sa.Numeric(18, 8), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("counterparty", sa.String(50), nullable=True),
        sa.Column("roll_from_id", PG_UUID(), nullable=True),
        sa.Column("close_rate", sa.Numeric(18, 8), nullable=True),
        sa.Column("close_spot", sa.Numeric(18, 8), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=True),
        sa.Column("mtm_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("mtm_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_fxfwd_portfolio", "fx_forwards", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_fxfwd_status", "fx_forwards", ["status"], schema=SCHEMA)
    op.create_index("ix_fxfwd_maturity", "fx_forwards", ["maturity_date"], schema=SCHEMA)
    op.create_index(
        "ix_fxfwd_pair",
        "fx_forwards",
        ["base_currency", "quote_currency"],
        schema=SCHEMA,
    )

    # FX interest rates (simplified — no yield curve)
    op.create_table(
        "fx_interest_rates",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fxir_currency",
        "fx_interest_rates",
        ["currency"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_fxir_currency", table_name="fx_interest_rates", schema=SCHEMA)
    op.drop_table("fx_interest_rates", schema=SCHEMA)
    op.drop_index("ix_fxfwd_pair", table_name="fx_forwards", schema=SCHEMA)
    op.drop_index("ix_fxfwd_maturity", table_name="fx_forwards", schema=SCHEMA)
    op.drop_index("ix_fxfwd_status", table_name="fx_forwards", schema=SCHEMA)
    op.drop_index("ix_fxfwd_portfolio", table_name="fx_forwards", schema=SCHEMA)
    op.drop_table("fx_forwards", schema=SCHEMA)
