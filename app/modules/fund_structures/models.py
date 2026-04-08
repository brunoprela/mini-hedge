"""SQLAlchemy models for fund structures — stored in positions schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


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
        String(64), nullable=False, unique=True,
    )
    allocation_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class StrategyBookRecord(Base):
    """Hierarchical strategy book within a fund."""

    __tablename__ = "strategy_books"
    __table_args__ = (
        Index("ix_sb_fund_slug", "fund_slug"),
        Index("ix_sb_parent_id", "parent_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("positions.strategy_books.id"),
        nullable=True,
    )
    portfolio_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), nullable=True,
    )
    target_allocation_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=text("1.0"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class FundOfFundsHoldingRecord(Base):
    """A holding within a fund-of-funds structure."""

    __tablename__ = "fof_holdings"
    __table_args__ = (
        Index("ix_fof_slug", "fof_fund_slug"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fof_fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    underlying_fund_slug: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    underlying_fund_name: Mapped[str] = mapped_column(String(128), nullable=False)
    allocation_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    current_nav: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=text("0"),
    )
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
