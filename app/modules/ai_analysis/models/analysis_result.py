"""Analysis result model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class AnalysisResultRecord(Base):
    """Persisted AI analysis result."""

    __tablename__ = "ai_analysis_results"
    __table_args__ = (
        Index("ix_ai_analysis_type", "analysis_type"),
        Index("ix_ai_analysis_created", "created_at"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False)
    request_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    key_points: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    instruments: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
