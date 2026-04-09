"""Risk-based P&L attribution model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class RiskBasedRecord(Base):
    """Risk-based P&L attribution result."""

    __tablename__ = "attr_risk_based"
    __table_args__ = (
        Index("ix_rb_portfolio", "portfolio_id"),
        Index("ix_rb_period", "period_start", "period_end"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    systematic_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    idiosyncratic_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    systematic_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
