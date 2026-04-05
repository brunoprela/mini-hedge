"""SQLAlchemy models for the positions schema — event store + read models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

# --- Event Store (append-only, source of truth) ---


class PositionEventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "sequence_number"),
        Index("ix_pos_events_aggregate", "aggregate_id", "sequence_number"),
        Index("ix_pos_events_type", "event_type"),
        Index("ix_pos_events_created", "created_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# --- Read Model: Current Positions (denormalized for fast queries) ---


class CurrentPositionRecord(Base):
    __tablename__ = "current_positions"
    __table_args__ = (
        Index("ix_pos_current_portfolio", "portfolio_id"),
        Index("ix_pos_current_instrument", "instrument_id"),
        {"schema": "positions"},
    )

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal(0))
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    market_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    market_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal(0)
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# --- Read Model: Position Lots (cost basis tracking) ---


class LotRecord(Base):
    __tablename__ = "lots"
    __table_args__ = (
        CheckConstraint("quantity != 0", name="valid_lot"),
        Index("ix_pos_lots_position", "portfolio_id", "instrument_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
