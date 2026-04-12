"""Volatility surface model — implied vol grid points for options pricing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class VolatilitySurfaceRecord(Base):
    __tablename__ = "volatility_surfaces"
    __table_args__ = (
        Index("ix_vs_instrument_expiry", "instrument_id", "expiry"),
        Index("ix_vs_timestamp", "timestamp"),
        {"schema": "market_data"},
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    expiry: Mapped[date] = mapped_column(Date, primary_key=True)
    strike: Mapped[Decimal] = mapped_column(Numeric(18, 4), primary_key=True)
    implied_vol: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
