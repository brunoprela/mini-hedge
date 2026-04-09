"""API key model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class APIKeyRecord(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_platform_api_keys_hash", "key_hash", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="apikey")
    fund_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.funds.id"),
        nullable=False,
    )
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.users.id"),
        nullable=True,
    )
