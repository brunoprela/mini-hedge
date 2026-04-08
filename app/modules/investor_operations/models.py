"""SQLAlchemy models for investor operations — stored in the ``positions`` schema.

Fund-scoped tables: subscription_requests, redemption_requests, fund_terms.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "positions"


class SubscriptionRequestRecord(Base):
    """Multi-step subscription request with workflow state."""

    __tablename__ = "subscription_requests"
    __table_args__ = (
        Index("ix_sub_req_investor", "investor_id"),
        Index("ix_sub_req_state", "state"),
        Index("ix_sub_req_dealing_date", "dealing_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    share_class: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # KYC decision
    kyc_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kyc_decision_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kyc_notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Ops review
    ops_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ops_decision_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ops_notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # GP decision
    gp_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gp_decision_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Wire
    wire_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wire_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Dealing & execution
    dealing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nav_per_share: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    shares_issued: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    capital_transaction_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), nullable=True
    )
    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RedemptionRequestRecord(Base):
    """Multi-step redemption request with workflow state."""

    __tablename__ = "redemption_requests"
    __table_args__ = (
        Index("ix_red_req_investor", "investor_id"),
        Index("ix_red_req_state", "state"),
        Index("ix_red_req_dealing_date", "dealing_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notice_date: Mapped[date] = mapped_column(Date, nullable=False)
    earliest_redemption_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lock_up_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Gate
    gate_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gate_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    # Dealing & execution
    dealing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nav_per_share: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    shares_redeemed: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    # Payment
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capital_transaction_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), nullable=True
    )
    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FundTermsRecord(Base):
    """Share class terms: lock-up, gates, notice periods, dealing dates."""

    __tablename__ = "fund_terms"
    __table_args__ = (
        Index("ix_fund_terms_share_class", "share_class", unique=True),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    share_class: Mapped[str] = mapped_column(String(32), nullable=False)
    lock_up_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    notice_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    redemption_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, default="quarterly"
    )
    gate_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=text("0.25")
    )
    minimum_subscription: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("1000000")
    )
    minimum_redemption: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("100000")
    )
    dealing_day: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    payment_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestorKYCRecord(Base):
    """KYC/AML screening status — platform-scoped."""

    __tablename__ = "investor_kyc"
    __table_args__ = (
        Index("ix_investor_kyc_investor", "investor_id", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    kyc_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    aml_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    sanctions_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pep_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_of_funds_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accredited_investor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_screened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    screening_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    screening_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
