"""Option-specific attributes — extension of the base instrument."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class OptionExtensionRecord(Base):
    __tablename__ = "option_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    underlying_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id", ondelete="SET NULL"),
        nullable=True,
    )
    option_type: Mapped[str | None] = mapped_column(String(4), nullable=True)  # CALL, PUT
    exercise_style: Mapped[str | None] = mapped_column(String(16), nullable=True)  # american, european, bermudan
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)  # multiplier
    settlement_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # cash, physical
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
