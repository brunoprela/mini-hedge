"""Asset-class extension tables for fixed income, options, futures, FX, and swaps.

Revision ID: 004
Revises: 003
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "security_master"


def upgrade() -> None:
    # ── Fixed Income ─────────────────────────────────────────
    op.create_table(
        "fixed_income_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id"),
            primary_key=True,
        ),
        sa.Column("coupon_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("coupon_frequency", sa.Integer(), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("face_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("day_count_convention", sa.String(16), nullable=True),
        sa.Column("credit_rating", sa.String(8), nullable=True),
        sa.Column("issuer", sa.String(128), nullable=True),
        sa.Column("seniority", sa.String(32), nullable=True),
        sa.Column("callable", sa.Boolean(), nullable=True),
        sa.Column("putable", sa.Boolean(), nullable=True),
        schema=SCHEMA,
    )

    # ── Options ──────────────────────────────────────────────
    op.create_table(
        "option_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id"),
            primary_key=True,
        ),
        sa.Column("underlying_id", PG_UUID(), nullable=True),
        sa.Column("option_type", sa.String(4), nullable=True),
        sa.Column("exercise_style", sa.String(16), nullable=True),
        sa.Column("strike_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("contract_size", sa.Numeric(18, 4), nullable=True),
        sa.Column("settlement_type", sa.String(16), nullable=True),
        schema=SCHEMA,
    )

    # ── Futures ──────────────────────────────────────────────
    op.create_table(
        "future_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id"),
            primary_key=True,
        ),
        sa.Column("underlying_id", PG_UUID(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("contract_size", sa.Numeric(18, 4), nullable=True),
        sa.Column("tick_size", sa.Numeric(18, 8), nullable=True),
        sa.Column("tick_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("margin_initial", sa.Numeric(18, 2), nullable=True),
        sa.Column("margin_maintenance", sa.Numeric(18, 2), nullable=True),
        sa.Column("settlement_type", sa.String(16), nullable=True),
        sa.Column("last_trading_date", sa.Date(), nullable=True),
        sa.Column("first_notice_date", sa.Date(), nullable=True),
        schema=SCHEMA,
    )

    # ── FX ───────────────────────────────────────────────────
    op.create_table(
        "fx_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id"),
            primary_key=True,
        ),
        sa.Column("base_currency", sa.String(3), nullable=True),
        sa.Column("quote_currency", sa.String(3), nullable=True),
        sa.Column("pip_size", sa.Numeric(10, 8), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("settlement_days", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

    # ── Swaps ────────────────────────────────────────────────
    op.create_table(
        "swap_extensions",
        sa.Column(
            "instrument_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id"),
            primary_key=True,
        ),
        sa.Column("swap_type", sa.String(32), nullable=True),
        sa.Column("notional_currency", sa.String(3), nullable=True),
        sa.Column("fixed_rate", sa.Numeric(10, 6), nullable=True),
        sa.Column("floating_index", sa.String(32), nullable=True),
        sa.Column("floating_spread", sa.Numeric(10, 6), nullable=True),
        sa.Column("payment_frequency", sa.String(16), nullable=True),
        sa.Column("day_count_convention", sa.String(16), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("underlying_id", PG_UUID(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("swap_extensions", schema=SCHEMA)
    op.drop_table("fx_extensions", schema=SCHEMA)
    op.drop_table("future_extensions", schema=SCHEMA)
    op.drop_table("option_extensions", schema=SCHEMA)
    op.drop_table("fixed_income_extensions", schema=SCHEMA)
