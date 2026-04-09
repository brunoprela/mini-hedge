"""EODRunStepRecord model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class EODRunStepRecord(Base):
    """Individual step within an EOD run."""

    __tablename__ = "run_steps"
    __table_args__ = ({"schema": SCHEMA},)

    run_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.runs.run_id"),
        primary_key=True,
    )
    step: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
