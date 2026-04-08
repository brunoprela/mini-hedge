"""Investor operations — subscription/redemption requests, fund terms.

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
SCHEMA = "positions"


def upgrade() -> None:
    # --- Subscription Requests ---
    op.create_table(
        "subscription_requests",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("investor_id", PG_UUID(), nullable=False),
        sa.Column("share_class", sa.String(32), nullable=False, server_default="default"),
        sa.Column("requested_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        # KYC
        sa.Column("kyc_decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kyc_decision_by", sa.String(255), nullable=True),
        sa.Column("kyc_notes", sa.String(1024), nullable=True),
        # Ops
        sa.Column("ops_decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ops_decision_by", sa.String(255), nullable=True),
        sa.Column("ops_notes", sa.String(1024), nullable=True),
        # GP
        sa.Column("gp_decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gp_decision_by", sa.String(255), nullable=True),
        # Wire
        sa.Column("wire_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wire_reference", sa.String(128), nullable=True),
        # Dealing & execution
        sa.Column("dealing_date", sa.Date(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nav_per_share", sa.Numeric(18, 6), nullable=True),
        sa.Column("shares_issued", sa.Numeric(18, 6), nullable=True),
        sa.Column("capital_transaction_id", PG_UUID(), nullable=True),
        # Cancellation
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(512), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_sub_req_investor", "subscription_requests", ["investor_id"], schema=SCHEMA)
    op.create_index("ix_sub_req_state", "subscription_requests", ["state"], schema=SCHEMA)
    op.create_index(
        "ix_sub_req_dealing_date", "subscription_requests", ["dealing_date"], schema=SCHEMA
    )

    # --- Redemption Requests ---
    op.create_table(
        "redemption_requests",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("investor_id", PG_UUID(), nullable=False),
        sa.Column("requested_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("notice_date", sa.Date(), nullable=False),
        sa.Column("earliest_redemption_date", sa.Date(), nullable=True),
        sa.Column("lock_up_expiry_date", sa.Date(), nullable=True),
        # Gate
        sa.Column("gate_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("gate_pct", sa.Numeric(8, 6), nullable=True),
        # Dealing & execution
        sa.Column("dealing_date", sa.Date(), nullable=True),
        sa.Column("nav_per_share", sa.Numeric(18, 6), nullable=True),
        sa.Column("shares_redeemed", sa.Numeric(18, 6), nullable=True),
        # Payment
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("payment_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_reference", sa.String(128), nullable=True),
        sa.Column("capital_transaction_id", PG_UUID(), nullable=True),
        # Cancellation
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(512), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_red_req_investor", "redemption_requests", ["investor_id"], schema=SCHEMA)
    op.create_index("ix_red_req_state", "redemption_requests", ["state"], schema=SCHEMA)
    op.create_index(
        "ix_red_req_dealing_date", "redemption_requests", ["dealing_date"], schema=SCHEMA
    )

    # --- Fund Terms ---
    op.create_table(
        "fund_terms",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("share_class", sa.String(32), nullable=False),
        sa.Column("lock_up_months", sa.Integer(), nullable=False, server_default=sa.text("12")),
        sa.Column("notice_period_days", sa.Integer(), nullable=False, server_default=sa.text("45")),
        sa.Column(
            "redemption_frequency", sa.String(32), nullable=False,
            server_default="quarterly",
        ),
        sa.Column("gate_pct", sa.Numeric(8, 6), nullable=False, server_default=sa.text("0.25")),
        sa.Column(
            "minimum_subscription", sa.Numeric(18, 2), nullable=False,
            server_default=sa.text("1000000"),
        ),
        sa.Column(
            "minimum_redemption", sa.Numeric(18, 2), nullable=False,
            server_default=sa.text("100000"),
        ),
        sa.Column("dealing_day", sa.Integer(), nullable=False, server_default=sa.text("-1")),
        sa.Column("payment_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fund_terms_share_class", "fund_terms", ["share_class"],
        unique=True, schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("fund_terms", schema=SCHEMA)
    op.drop_table("redemption_requests", schema=SCHEMA)
    op.drop_table("subscription_requests", schema=SCHEMA)
