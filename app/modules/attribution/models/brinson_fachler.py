"""Brinson-Fachler attribution model."""

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


class BrinsonFachlerRecord(Base):
    """Brinson-Fachler attribution result."""

    __tablename__ = "attr_brinson_fachler"
    __table_args__ = (
        Index("ix_bf_portfolio", "portfolio_id"),
        Index("ix_bf_period", "period_start", "period_end"),
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
    portfolio_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    active_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    total_allocation: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    total_selection: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    total_interaction: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
