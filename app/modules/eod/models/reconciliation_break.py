"""ReconciliationBreakRecord model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class ReconciliationBreakRecord(Base):
    """Individual reconciliation break with resolution lifecycle."""

    __tablename__ = "reconciliation_breaks"
    __table_args__ = (
        Index("ix_recon_breaks_portfolio_date", "portfolio_id", "business_date"),
        Index("ix_recon_breaks_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    break_type: Mapped[str] = mapped_column(String(32), nullable=False)
    internal_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    broker_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    admin_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    difference: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    is_material: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Cash break fields
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    internal_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    admin_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # Resolution lifecycle
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'open'"))
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
