"""Alt data point model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
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


class AltDataPointRecord(Base):
    """Individual alternative data observation."""

    __tablename__ = "alt_data_points"
    __table_args__ = (
        Index("ix_altpt_feed_ts", "feed_id", "timestamp"),
        Index("ix_altpt_instrument_ts", "instrument_id", "timestamp"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    feed_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.alt_data_feeds.id"),
        nullable=False,
    )
    instrument_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
