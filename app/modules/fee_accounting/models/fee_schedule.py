"""Fee schedule model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class FeeScheduleRecord(Base):
    __tablename__ = "fee_schedules"
    __table_args__ = (
        Index("ix_fee_schedules_fund_class", "fund_slug", "share_class", unique=True),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    share_class: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    management_fee_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_fee_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    hurdle_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    high_water_mark: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    crystallization_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
