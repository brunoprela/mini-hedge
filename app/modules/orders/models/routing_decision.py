"""RoutingDecisionRecord model."""

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


class RoutingDecisionRecord(Base):
    __tablename__ = "routing_decisions"
    __table_args__ = (
        Index("ix_routing_decisions_order_id", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rule_ids_matched: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
