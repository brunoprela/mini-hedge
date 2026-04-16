"""Portfolio model."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class PortfolioRecord(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        Index("ix_platform_portfolios_fund", "fund_id"),
        sa.UniqueConstraint("fund_id", "slug", name="uq_portfolios_fund_slug"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    fund_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("platform.funds.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
