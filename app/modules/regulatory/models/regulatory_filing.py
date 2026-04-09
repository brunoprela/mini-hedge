"""Regulatory filing model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Date, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class RegulatoryFilingRecord(Base):
    """Tracks generated regulatory filings (Form PF, 13F, etc.)."""

    __tablename__ = "regulatory_filings"
    __table_args__ = (
        Index("ix_reg_filing_type", "filing_type"),
        Index("ix_reg_filing_period", "reporting_period"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    filing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reporting_period: Mapped[datetime] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
