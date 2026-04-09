"""Factor model decomposition record."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class FactorExposureRecord(Base):
    """Factor model decomposition record."""

    __tablename__ = "risk_factor_exposures"
    __table_args__ = (
        Index("ix_factor_snapshot", "snapshot_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    factor: Mapped[str] = mapped_column(String(30), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    exposure_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
