"""RoutingRuleRecord model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class RoutingRuleRecord(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        Index("ix_routing_rules_fund", "fund_slug"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    min_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    max_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    preferred_broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
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
