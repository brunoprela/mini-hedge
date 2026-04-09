"""Capital transaction model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CapitalTransactionRecord(Base):
    """Immutable ledger of all capital movements."""

    __tablename__ = "capital_transactions"
    __table_args__ = (
        Index("ix_ct_account", "capital_account_id"),
        Index("ix_ct_type", "transaction_type"),
        Index("ix_ct_date", "business_date"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    capital_account_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    nav_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
