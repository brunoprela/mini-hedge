"""Restricted instrument model — per-fund restricted securities list."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class RestrictedInstrumentRecord(Base):
    __tablename__ = "restricted_instruments"
    __table_args__ = (
        UniqueConstraint("fund_slug", "instrument_id", name="uq_restricted_fund_instrument"),
        Index("ix_restricted_fund_slug", "fund_slug"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    added_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
