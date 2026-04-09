"""Per-position impact from a stress test."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class StressPositionImpactRecord(Base):
    """Per-position impact from a stress test."""

    __tablename__ = "risk_stress_position_impacts"
    __table_args__ = (
        Index("ix_stress_impact_result", "stress_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    stress_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl_impact: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_change: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
