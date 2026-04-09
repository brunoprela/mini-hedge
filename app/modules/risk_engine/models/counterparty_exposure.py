"""Point-in-time exposure to a counterparty."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CounterpartyExposureRecord(Base):
    """Point-in-time exposure to a counterparty."""

    __tablename__ = "risk_counterparty_exposures"
    __table_args__ = (
        Index("ix_cpty_exp_cpty", "counterparty_id"),
        Index("ix_cpty_exp_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    counterparty_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    business_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    collateral_held: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    collateral_posted: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    utilization_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    breach: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
