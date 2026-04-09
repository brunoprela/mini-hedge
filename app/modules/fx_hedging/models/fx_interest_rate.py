"""FX interest rate model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FXInterestRateRecord(Base):
    """Simplified interest rates per currency (no yield curve)."""

    __tablename__ = "fx_interest_rates"
    __table_args__ = (
        Index("ix_fxir_currency", "currency"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
