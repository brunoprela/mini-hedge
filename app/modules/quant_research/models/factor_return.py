"""Factor return model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FactorReturnRecord(Base):
    """Daily factor return time series."""

    __tablename__ = "factor_returns"
    __table_args__ = (
        Index("ix_fret_factor_date", "factor_id", "return_date"),
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
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    cumulative_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
