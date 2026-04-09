"""Point-in-time risk metrics for a portfolio."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class RiskSnapshotRecord(Base):
    """Point-in-time risk metrics for a portfolio."""

    __tablename__ = "risk_snapshots"
    __table_args__ = (
        Index("ix_risk_snap_portfolio", "portfolio_id"),
        Index("ix_risk_snap_time", "snapshot_at"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_95_1d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_99_1d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    expected_shortfall_95: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
