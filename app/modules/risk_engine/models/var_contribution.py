"""Per-instrument VaR contribution."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class VaRContributionRecord(Base):
    """Per-instrument VaR contribution."""

    __tablename__ = "risk_var_contributions"
    __table_args__ = (
        Index("ix_var_contrib_result", "var_result_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    var_result_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    marginal_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    component_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pct_contribution: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
