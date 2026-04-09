"""Optimization run model."""

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
