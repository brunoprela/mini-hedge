"""SQLAlchemy model for block allocations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class BlockAllocationRecord(Base):
    __tablename__ = "block_allocations"
    __table_args__ = (
        Index("ix_platform_block_alloc_state", "state"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="market")
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    algo_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    algo_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    execution_fund_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_order_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
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
