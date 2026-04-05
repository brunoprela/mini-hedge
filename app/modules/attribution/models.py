"""SQLAlchemy models for performance attribution — stored in fund schemas."""

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
from sqlalchemy.dialects.postgresql import JSONB
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


class BrinsonFachlerSectorRecord(Base):
    """Per-sector Brinson-Fachler breakdown."""

    __tablename__ = "attr_brinson_fachler_sectors"
    __table_args__ = (
        Index("ix_bf_sector_result", "bf_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    bf_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    sector: Mapped[str] = mapped_column(String(50), nullable=False)
    portfolio_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    benchmark_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    portfolio_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    allocation_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    selection_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    interaction_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    total_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)


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


class RiskFactorContributionRecord(Base):
    """Per-factor contribution to risk-based attribution."""

    __tablename__ = "attr_risk_factor_contributions"
    __table_args__ = (
        Index("ix_rfc_result", "rb_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rb_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    factor: Mapped[str] = mapped_column(String(100), nullable=False)
    factor_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    portfolio_exposure: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    pnl_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)


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
    periods: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
