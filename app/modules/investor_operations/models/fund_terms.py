"""FundTermsRecord — share class terms: lock-up, gates, notice periods, dealing dates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "positions"


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
