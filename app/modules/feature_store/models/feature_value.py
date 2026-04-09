"""Feature value model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FeatureValueRecord(Base):
    """A computed feature value for a specific entity at a point in time."""

    __tablename__ = "feature_values"
    __table_args__ = (
        Index("ix_featval_feature_entity_ts", "feature_id", "entity_id", "computed_at"),
        Index("ix_featval_entity", "entity_id"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    feature_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.feature_definitions.id"),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )
    value_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
