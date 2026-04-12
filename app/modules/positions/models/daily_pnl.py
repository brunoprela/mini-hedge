"""Daily P&L snapshot model."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class DailyPnLRecord(Base):
    __tablename__ = "daily_pnl"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "instrument_id", "business_date", name="uq_daily_pnl_position_date"
        ),
        Index("ix_pos_daily_pnl_portfolio_date", "portfolio_id", "business_date"),
        Index("ix_pos_daily_pnl_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    market_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
