"""Swap-specific attributes — extension of the base instrument."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class SwapExtensionRecord(Base):
    __tablename__ = "swap_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id"),
        primary_key=True,
    )
    swap_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # interest_rate, credit_default, total_return, equity
    notional_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fixed_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    floating_index: Mapped[str | None] = mapped_column(String(32), nullable=True)  # SOFR, EURIBOR, etc.
    floating_spread: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)  # bps over index
    payment_frequency: Mapped[str | None] = mapped_column(String(16), nullable=True)  # monthly, quarterly, semi_annual
    day_count_convention: Mapped[str | None] = mapped_column(String(16), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    underlying_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
