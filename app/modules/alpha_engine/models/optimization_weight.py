"""Optimization weight model."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class OptimizationWeightRecord(Base):
    """Per-instrument target weight from optimization."""

    __tablename__ = "alpha_optimization_weights"
    __table_args__ = (
        Index("ix_opt_weight_run", "optimization_run_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    optimization_run_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    current_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    delta_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    delta_shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    delta_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
