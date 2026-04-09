"""Current position model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CurrentPositionRecord(Base):
    __tablename__ = "current_positions"
    __table_args__ = (
        Index("ix_pos_current_portfolio", "portfolio_id"),
        Index("ix_pos_current_instrument", "instrument_id"),
        {"schema": "positions"},
    )

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    market_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    market_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
