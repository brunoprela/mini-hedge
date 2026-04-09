"""BrokerScorecardRecord model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class BrokerScorecardRecord(Base):
    __tablename__ = "broker_scorecards"
    __table_args__ = (
        Index("ix_broker_scorecards_broker_id", "broker_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_orders: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    total_fills: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    total_rejects: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    avg_slippage_bps: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    avg_fill_time_ms: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    avg_cost_bps: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    fill_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("0")
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
