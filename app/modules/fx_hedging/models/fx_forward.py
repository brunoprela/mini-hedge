"""FX forward model."""

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


class FXForwardRecord(Base):
    """An OTC FX forward contract."""

    __tablename__ = "fx_forwards"
    __table_args__ = (
        Index("ix_fxfwd_portfolio", "portfolio_id"),
        Index("ix_fxfwd_status", "status"),
        Index("ix_fxfwd_maturity", "maturity_date"),
        Index("ix_fxfwd_pair", "base_currency", "quote_currency"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    spot_at_inception: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'open'"),
    )
    counterparty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    roll_from_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
    )
    close_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    close_spot: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    mtm_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    mtm_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
