"""Future-specific attributes — extension of the base instrument."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FutureExtensionRecord(Base):
    __tablename__ = "future_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id"),
        primary_key=True,
    )
    underlying_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    tick_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    margin_initial: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    margin_maintenance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    settlement_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # cash, physical
    last_trading_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_notice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
