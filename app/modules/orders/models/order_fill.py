"""OrderFillRecord model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class OrderFillRecord(Base):
    __tablename__ = "order_fills"
    __table_args__ = (
        Index("ix_order_fills_order", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("positions.orders.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    broker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commission: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
