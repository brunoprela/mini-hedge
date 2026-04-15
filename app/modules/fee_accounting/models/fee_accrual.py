"""Fee accrual model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FeeAccrualRecord(Base):
    __tablename__ = "fee_accruals"
    __table_args__ = (
        Index("ix_fee_accruals_portfolio", "portfolio_id"),
        Index("ix_fee_accruals_date", "accrual_date"),
        Index("ix_fee_accruals_status", "status"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    share_class: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    fee_type: Mapped[str] = mapped_column(String(16), nullable=False)
    accrual_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_basis: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    accrued_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cumulative_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
