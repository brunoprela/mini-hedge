"""Stress test scenario result."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


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
