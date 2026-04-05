"""SQLAlchemy models for EOD processing — stored in the ``eod`` schema."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class EODRunRecord(Base):
    """Tracks a full EOD run for a fund on a business date."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_eod_runs_date", "business_date"),
        Index("ix_eod_runs_fund", "fund_slug"),
        {"schema": SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_successful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EODRunStepRecord(Base):
    """Individual step within an EOD run."""

    __tablename__ = "run_steps"
    __table_args__ = ({"schema": SCHEMA},)

    run_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.runs.run_id"),
        primary_key=True,
    )
    step: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class FinalizedPriceRecord(Base):
    """Locked closing price for an instrument on a business date."""

    __tablename__ = "finalized_prices"
    __table_args__ = (
        Index("ix_finalized_prices_date", "business_date"),
        {"schema": SCHEMA},
    )

    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_by: Mapped[str] = mapped_column(String(64), nullable=False)


class NAVSnapshotRecord(Base):
    """NAV snapshot for a portfolio on a business date."""

    __tablename__ = "nav_snapshots"
    __table_args__ = ({"schema": SCHEMA},)

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    accrued_fees: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    nav_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    shares_outstanding: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PnLSnapshotRecord(Base):
    """Frozen daily P&L for a portfolio."""

    __tablename__ = "pnl_snapshots"
    __table_args__ = ({"schema": SCHEMA},)

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    position_count: Mapped[int] = mapped_column(nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReconciliationRecord(Base):
    """Position reconciliation result for a portfolio."""

    __tablename__ = "reconciliation_results"
    __table_args__ = ({"schema": SCHEMA},)

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_positions: Mapped[int] = mapped_column(nullable=False)
    matched_positions: Mapped[int] = mapped_column(nullable=False)
    is_clean: Mapped[bool] = mapped_column(Boolean, nullable=False)
    breaks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
