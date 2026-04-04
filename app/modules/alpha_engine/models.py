"""SQLAlchemy models for alpha engine — stored in fund schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
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


class ScenarioRunRecord(Base):
    """What-if scenario run."""

    __tablename__ = "alpha_scenario_runs"
    __table_args__ = (
        Index("ix_scenario_portfolio", "portfolio_id"),
        Index("ix_scenario_time", "created_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    trades: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    result_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OptimizationRunRecord(Base):
    """Portfolio optimization run."""

    __tablename__ = "alpha_optimization_runs"
    __table_args__ = (
        Index("ix_opt_portfolio", "portfolio_id"),
        Index("ix_opt_time", "created_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    objective: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    expected_risk: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OptimizationWeightRecord(Base):
    """Per-instrument target weight from optimization."""

    __tablename__ = "alpha_optimization_weights"
    __table_args__ = (
        Index("ix_opt_weight_run", "optimization_run_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    optimization_run_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(20), nullable=False)
    current_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    delta_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    delta_shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    delta_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class OrderIntentRecord(Base):
    """Generated order intent from optimization."""

    __tablename__ = "alpha_order_intents"
    __table_args__ = (
        Index("ix_intent_run", "optimization_run_id"),
        Index("ix_intent_status", "status"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    optimization_run_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
