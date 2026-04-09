"""Capital account model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CapitalAccountRecord(Base):
    """Daily snapshot of an investor's capital in a fund."""

    __tablename__ = "capital_accounts"
    __table_args__ = (
        Index("ix_ca_investor_date", "investor_id", "effective_date"),
        Index("ix_ca_effective_date", "effective_date"),
        Index("ix_ca_share_class", "share_class"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    share_class: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    beginning_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    contributions: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    withdrawals: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    pnl_allocation: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    management_fee_allocation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    performance_fee_allocation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    ending_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=0)
    shares_held: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
