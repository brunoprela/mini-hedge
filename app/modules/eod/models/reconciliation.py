"""ReconciliationRecord model."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class ReconciliationRecord(Base):
    """Position reconciliation result for a portfolio."""

    __tablename__ = "reconciliation_results"
    __table_args__ = ({"schema": SCHEMA},)

    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_positions: Mapped[int] = mapped_column(nullable=False)
    matched_positions: Mapped[int] = mapped_column(nullable=False)
    is_clean: Mapped[bool] = mapped_column(Boolean, nullable=False)
    breaks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=list)
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
