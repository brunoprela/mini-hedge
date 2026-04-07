"""SQLAlchemy models for the market_data schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


class PriceRecord(Base):
    __tablename__ = "prices"
    __table_args__ = (
        Index("ix_md_prices_instrument_time", "instrument_id", "timestamp"),
        {"schema": "market_data"},
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    bid: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    ask: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    mid: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)


class FXRateRecord(Base):
    """Spot FX rates — 1 unit of base_currency = rate units of quote_currency."""

    __tablename__ = "fx_rates"
    __table_args__ = (
        Index("ix_md_fx_rates_pair_time", "base_currency", "quote_currency", "timestamp"),
        {"schema": "market_data"},
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    quote_currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
