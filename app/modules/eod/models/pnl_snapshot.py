"""PnLSnapshotRecord model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


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
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
