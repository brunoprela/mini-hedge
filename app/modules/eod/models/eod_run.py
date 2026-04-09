"""EODRunRecord model."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base

SCHEMA = "eod"


class EODRunRecord(Base):
    """Tracks a full EOD run for a fund on a business date."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_eod_runs_date", "business_date"),
        Index("ix_eod_runs_fund", "fund_slug"),
        {"schema": SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_successful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
