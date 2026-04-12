"""FX-specific attributes — extension of the base instrument."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FXExtensionRecord(Base):
    __tablename__ = "fx_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id"),
        primary_key=True,
    )
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    pip_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settlement_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # T+0, T+1, T+2
