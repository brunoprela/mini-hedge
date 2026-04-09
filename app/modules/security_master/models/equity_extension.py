"""Equity extension model."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class EquityExtensionRecord(Base):
    """Equity-specific attributes — extension of the base instrument."""

    __tablename__ = "equity_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id"),
        primary_key=True,
    )
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    free_float_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
