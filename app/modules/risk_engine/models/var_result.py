"""Detailed VaR calculation result."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class VaRResultRecord(Base):
    """Detailed VaR calculation result."""

    __tablename__ = "risk_var_results"
    __table_args__ = (
        Index("ix_var_portfolio", "portfolio_id"),
        Index("ix_var_time", "calculated_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    var_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    expected_shortfall: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
