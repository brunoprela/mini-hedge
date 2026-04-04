"""SQLAlchemy models for risk engine — stored in fund schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RiskSnapshotRecord(Base):
    """Point-in-time risk metrics for a portfolio."""

    __tablename__ = "risk_snapshots"
    __table_args__ = (
        Index("ix_risk_snap_portfolio", "portfolio_id"),
        Index("ix_risk_snap_time", "snapshot_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_95_1d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_99_1d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_shortfall_95: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


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


class VaRContributionRecord(Base):
    """Per-instrument VaR contribution."""

    __tablename__ = "risk_var_contributions"
    __table_args__ = (
        Index("ix_var_contrib_result", "var_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    var_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(20), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    marginal_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    component_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_contribution: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)


class StressTestResultRecord(Base):
    """Stress test scenario result."""

    __tablename__ = "risk_stress_results"
    __table_args__ = (
        Index("ix_stress_portfolio", "portfolio_id"),
        Index("ix_stress_time", "calculated_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)
    shocks: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    total_pnl_impact: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_pct_change: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StressPositionImpactRecord(Base):
    """Per-position impact from a stress test."""

    __tablename__ = "risk_stress_position_impacts"
    __table_args__ = (
        Index("ix_stress_impact_result", "stress_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    stress_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(20), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl_impact: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_change: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)


class FactorExposureRecord(Base):
    """Factor model decomposition record."""

    __tablename__ = "risk_factor_exposures"
    __table_args__ = (
        Index("ix_factor_snapshot", "snapshot_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    factor: Mapped[str] = mapped_column(String(30), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    exposure_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
