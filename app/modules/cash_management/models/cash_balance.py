"""CashBalanceRecord — current cash balance per portfolio per currency."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


class CashBalanceRecord(Base):
    """Current cash balance per portfolio per currency."""

    __tablename__ = "cash_balances"
    __table_args__ = (
        Index("ix_cash_bal_portfolio", "portfolio_id"),
        Index(
            "ix_cash_bal_portfolio_ccy",
            "portfolio_id",
            "currency",
            unique=True,
        ),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    pending_inflows: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    pending_outflows: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
