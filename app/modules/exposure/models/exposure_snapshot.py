"""SQLAlchemy models for exposure snapshots — stored in fund schemas."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base as Base

_SCHEMA = "positions"


class ExposureSnapshotRecord(Base):
    __tablename__ = "exposure_snapshots"
    __table_args__ = (
        Index("ix_exp_snapshot_portfolio", "portfolio_id"),
        Index("ix_exp_snapshot_time", "snapshot_at"),
        {"schema": _SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    long_count: Mapped[int] = mapped_column(Integer, nullable=False)
    short_count: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdowns: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    breakdown_rows: Mapped[list[ExposureSnapshotBreakdownRecord]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ExposureSnapshotBreakdownRecord(Base):
    """Relational sub-table for per-dimension exposure breakdowns."""

    __tablename__ = "exposure_snapshot_breakdowns"
    __table_args__ = (
        Index("ix_exp_bd_snapshot", "snapshot_id"),
        Index("ix_exp_bd_dimension_key", "dimension", "key"),
        {"schema": _SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey(f"{_SCHEMA}.exposure_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    long_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    short_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    gross_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    weight_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)

    snapshot: Mapped[ExposureSnapshotRecord] = relationship(
        back_populates="breakdown_rows",
    )
