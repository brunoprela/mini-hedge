"""CashProjectionRecord — persisted cash projection snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CashProjectionRecord(Base):
    """Persisted cash projection snapshot."""

    __tablename__ = "cash_projections"
    __table_args__ = (
        Index("ix_proj_portfolio", "portfolio_id"),
        Index("ix_proj_time", "projected_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    horizon_days: Mapped[int] = mapped_column(nullable=False)
    entries: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
