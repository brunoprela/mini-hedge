"""SQLAlchemy models for cash management — stored in fund schemas."""

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CashBalanceRecord(Base):
    """Current cash balance per portfolio per currency."""

    __tablename__ = "cash_balances"
    __table_args__ = (
        Index("ix_cash_bal_portfolio", "portfolio_id"),
        Index(
            "ix_cash_bal_portfolio_ccy",
            "portfolio_id",
            "currency",
            unique=True,
        ),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    pending_inflows: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    pending_outflows: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CashJournalRecord(Base):
    """Double-entry cash journal for audit trail."""

    __tablename__ = "cash_balance_journal"
    __table_args__ = (
        Index("ix_cash_journal_portfolio", "portfolio_id"),
        Index("ix_cash_journal_time", "created_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    flow_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CashSettlementRecord(Base):
    """Trade settlement tracking."""

    __tablename__ = "cash_settlements"
    __table_args__ = (
        Index("ix_settle_portfolio", "portfolio_id"),
        Index("ix_settle_date", "settlement_date"),
        Index("ix_settle_status", "status"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    order_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    instrument_id: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ScheduledFlowRecord(Base):
    """Known future cash flows (dividends, fees, subscriptions)."""

    __tablename__ = "cash_scheduled_flows"
    __table_args__ = (
        Index("ix_sched_portfolio", "portfolio_id"),
        Index("ix_sched_date", "flow_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    flow_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    flow_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CashProjectionRecord(Base):
    """Persisted cash projection snapshot."""

    __tablename__ = "cash_projections"
    __table_args__ = (
        Index("ix_proj_portfolio", "portfolio_id"),
        Index("ix_proj_time", "projected_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    horizon_days: Mapped[int] = mapped_column(nullable=False)
    entries: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
