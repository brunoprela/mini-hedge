"""High water mark model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class HighWaterMarkRecord(Base):
    __tablename__ = "high_water_marks"
    __table_args__ = (
        Index("ix_high_water_marks_portfolio", "portfolio_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    share_class: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    hwm_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    hwm_nav: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    peak_nav: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
