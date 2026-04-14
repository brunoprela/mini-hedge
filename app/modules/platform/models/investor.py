"""Investor model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class InvestorRecord(Base):
    """Platform-scoped investor registry — investors can invest in multiple funds."""

    __tablename__ = "investors"
    __table_args__ = (
        Index("ix_platform_investors_entity_type", "entity_type"),
        Index("ix_platform_investors_active", "is_active"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    keycloak_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # individual, institution, fund_of_funds
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
