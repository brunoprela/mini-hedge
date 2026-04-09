"""Cumulative multi-period attribution model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CumulativeAttributionRecord(Base):
    """Cumulative multi-period attribution (Carino linked)."""

    __tablename__ = "attr_cumulative"
    __table_args__ = (
        Index("ix_cum_portfolio", "portfolio_id"),
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
    cumulative_portfolio_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cumulative_benchmark_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cumulative_active_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cumulative_allocation: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cumulative_selection: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cumulative_interaction: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    periods: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
