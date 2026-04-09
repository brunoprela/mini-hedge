"""RedemptionRequestRecord — multi-step redemption request with workflow state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
