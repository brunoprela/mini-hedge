"""Portfolio liquidity profile snapshot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Index, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class LiquidityProfileRecord(Base):
    """Portfolio liquidity profile snapshot."""

    __tablename__ = "risk_liquidity_profiles"
    __table_args__ = (
        Index("ix_liq_portfolio", "portfolio_id"),
        Index("ix_liq_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    business_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_nav: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pct_1_day: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    pct_1_week: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    pct_1_month: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    pct_3_months: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    pct_illiquid: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    weighted_days_to_liquidate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    redemption_coverage_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        default=Decimal("1.0"),
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
