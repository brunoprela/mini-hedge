"""Per-factor contribution to risk-based attribution model."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class RiskFactorContributionRecord(Base):
    """Per-factor contribution to risk-based attribution."""

    __tablename__ = "attr_risk_factor_contributions"
    __table_args__ = (
        Index("ix_rfc_result", "rb_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rb_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    factor: Mapped[str] = mapped_column(String(100), nullable=False)
    factor_return: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    portfolio_exposure: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    pnl_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
