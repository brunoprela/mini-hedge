"""Per-sector Brinson-Fachler breakdown model."""

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


class BrinsonFachlerSectorRecord(Base):
    """Per-sector Brinson-Fachler breakdown."""

    __tablename__ = "attr_brinson_fachler_sectors"
    __table_args__ = (
        Index("ix_bf_sector_result", "bf_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    bf_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    sector: Mapped[str] = mapped_column(String(50), nullable=False)
    portfolio_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    benchmark_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    portfolio_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    allocation_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    selection_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    interaction_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    total_effect: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
