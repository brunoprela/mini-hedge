"""FinalizedPriceRecord model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class FinalizedPriceRecord(Base):
    """Locked closing price for an instrument on a business date."""

    __tablename__ = "finalized_prices"
    __table_args__ = (
        Index("ix_finalized_prices_date", "business_date"),
        {"schema": SCHEMA},
    )

    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_by: Mapped[str] = mapped_column(String(64), nullable=False)
