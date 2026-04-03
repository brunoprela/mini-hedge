"""SQLAlchemy models for exposure snapshots — stored in fund schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExposureSnapshotRecord(Base):
    __tablename__ = "exposure_snapshots"
    __table_args__ = (
        Index("ix_exp_snapshot_portfolio", "portfolio_id"),
        Index("ix_exp_snapshot_time", "snapshot_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), nullable=False
    )
    gross_exposure: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    net_exposure: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    long_exposure: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    short_exposure: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    long_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    short_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    breakdowns: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, default=dict
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
