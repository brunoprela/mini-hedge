"""SQLAlchemy models for risk engine — stored in fund schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


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
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
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
    shocks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
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


# ---------------------------------------------------------------------------
# 3A. Counterparty & Credit Risk
# ---------------------------------------------------------------------------


class CounterpartyRecord(Base):
    """Counterparty (broker, prime broker, custodian) definition."""

    __tablename__ = "risk_counterparties"
    __table_args__ = (
        Index("ix_cpty_name", "name"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    counterparty_type: Mapped[str] = mapped_column(String(32), nullable=False)
    credit_rating: Mapped[str | None] = mapped_column(String(8), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    netting_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CounterpartyExposureRecord(Base):
    """Point-in-time exposure to a counterparty."""

    __tablename__ = "risk_counterparty_exposures"
    __table_args__ = (
        Index("ix_cpty_exp_cpty", "counterparty_id"),
        Index("ix_cpty_exp_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    counterparty_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    business_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    collateral_held: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    collateral_posted: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    utilization_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    breach: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# ---------------------------------------------------------------------------
# 3B. Liquidity Risk
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 3C. Margin Management
# ---------------------------------------------------------------------------


class MarginRequirementRecord(Base):
    """Portfolio-level margin requirements and utilization."""

    __tablename__ = "risk_margin_requirements"
    __table_args__ = (
        Index("ix_margin_portfolio", "portfolio_id"),
        Index("ix_margin_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    business_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    initial_margin: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    maintenance_margin: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_available: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_excess_deficit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    margin_call_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
