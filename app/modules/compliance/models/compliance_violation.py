"""Compliance violation model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class ComplianceViolationRecord(Base):
    __tablename__ = "compliance_violations"
    __table_args__ = (
        Index("ix_comp_viol_portfolio", "portfolio_id"),
        Index("ix_comp_viol_rule", "rule_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    rule_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    limit_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    breach_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
