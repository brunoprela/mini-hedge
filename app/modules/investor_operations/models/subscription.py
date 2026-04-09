"""SubscriptionRequestRecord — multi-step subscription request with workflow state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    String,
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
