"""CashSettlementRecord — trade settlement tracking."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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


class CashSettlementRecord(Base):
    """Trade settlement tracking."""

    __tablename__ = "cash_settlements"
    __table_args__ = (
        Index("ix_settle_portfolio", "portfolio_id"),
        Index("ix_settle_date", "settlement_date"),
        Index("ix_settle_status", "status"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    order_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
