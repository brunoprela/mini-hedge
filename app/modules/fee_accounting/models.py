"""SQLAlchemy models for fee accounting — stored in the positions schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


class FeeScheduleRecord(Base):
    __tablename__ = "fee_schedules"
    __table_args__ = (
        Index("ix_fee_schedules_fund_slug", "fund_slug", unique=True),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    management_fee_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_fee_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    hurdle_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    high_water_mark: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    crystallization_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FeeAccrualRecord(Base):
    __tablename__ = "fee_accruals"
    __table_args__ = (
        Index("ix_fee_accruals_portfolio", "portfolio_id"),
        Index("ix_fee_accruals_date", "accrual_date"),
        Index("ix_fee_accruals_status", "status"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    fee_type: Mapped[str] = mapped_column(String(16), nullable=False)
    accrual_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    nav_basis: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    accrued_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cumulative_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HighWaterMarkRecord(Base):
    __tablename__ = "high_water_marks"
    __table_args__ = (
        Index("ix_high_water_marks_portfolio", "portfolio_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    hwm_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    hwm_nav: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    peak_nav: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
