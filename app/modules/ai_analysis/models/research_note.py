"""Research note model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class ResearchNoteRecord(Base):
    """User-created or AI-generated research note."""

    __tablename__ = "research_notes"
    __table_args__ = (
        Index("ix_research_notes_created", "created_at"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False)
    instruments: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tags: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
