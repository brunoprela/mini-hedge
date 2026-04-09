"""Counterparty (broker, prime broker, custodian) definition."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CounterpartyRecord(Base):
    """Counterparty (broker, prime broker, custodian) definition."""

    __tablename__ = "risk_counterparties"
    __table_args__ = (
        Index("ix_cpty_name", "name"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    counterparty_type: Mapped[str] = mapped_column(String(32), nullable=False)
    credit_rating: Mapped[str | None] = mapped_column(String(8), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    netting_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
