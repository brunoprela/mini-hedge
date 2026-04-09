"""Factor exposure model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FactorExposureRecord(Base):
    """Per-instrument factor exposure at a point in time."""

    __tablename__ = "factor_exposures"
    __table_args__ = (
        Index("ix_fexp_factor_date", "factor_id", "as_of_date"),
        Index("ix_fexp_instrument", "instrument_id"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    factor_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.factor_definitions.id"),
        nullable=False,
    )
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    z_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
