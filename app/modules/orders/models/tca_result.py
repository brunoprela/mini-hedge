"""TCAResultRecord model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class TCAResultRecord(Base):
    __tablename__ = "order_tca_results"
    __table_args__ = (
        Index("ix_tca_order_id", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, unique=True)

    # Benchmarks
    arrival_mid_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    arrival_spread: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    vwap_benchmark: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # Cost decomposition (basis points)
    total_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    commission_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    spread_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    market_impact_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    timing_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    opportunity_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    implementation_shortfall_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # Participation metrics
    participation_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    execution_duration_seconds: Mapped[int] = mapped_column(nullable=False)

    # Dollar amounts
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
