"""Performance letter model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Date, DateTime, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class PerformanceLetterRecord(Base):
    """Monthly performance letters."""

    __tablename__ = "performance_letters"
    __table_args__ = (
        Index("ix_perf_letter_period", "period"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    period: Mapped[datetime] = mapped_column(Date, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
