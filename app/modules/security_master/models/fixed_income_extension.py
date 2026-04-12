"""Fixed-income-specific attributes — extension of the base instrument."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FixedIncomeExtensionRecord(Base):
    __tablename__ = "fixed_income_extensions"
    __table_args__ = {"schema": "security_master"}

    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id"),
        primary_key=True,
    )
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    coupon_frequency: Mapped[int | None] = mapped_column(nullable=True)  # payments per year
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    face_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    day_count_convention: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ACT/360, 30/360, etc.
    credit_rating: Mapped[str | None] = mapped_column(String(8), nullable=True)  # AAA, BB+, etc.
    issuer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)  # senior, subordinated, etc.
    callable: Mapped[bool | None] = mapped_column(nullable=True)
    putable: Mapped[bool | None] = mapped_column(nullable=True)
