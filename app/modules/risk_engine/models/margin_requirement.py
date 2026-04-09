"""Portfolio-level margin requirements and utilization."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


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
