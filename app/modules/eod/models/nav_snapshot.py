"""NAVSnapshotRecord model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class NAVSnapshotRecord(Base):
    """NAV snapshot for a portfolio on a business date."""

    __tablename__ = "nav_snapshots"
    __table_args__ = ({"schema": SCHEMA},)

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    accrued_fees: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    nav_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    shares_outstanding: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
