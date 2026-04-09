"""Master-feeder link model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class MasterFeederLinkRecord(Base):
    """Links a feeder fund to its master fund."""

    __tablename__ = "master_feeder_links"
    __table_args__ = (
        Index("ix_mf_master_slug", "master_fund_slug"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    master_fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    feeder_fund_slug: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    allocation_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 6),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
