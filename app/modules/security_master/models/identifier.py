"""Instrument identifier model — maps external IDs (ISIN, CUSIP, etc.) to instruments."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class IdentifierType(StrEnum):
    TICKER = "ticker"
    ISIN = "isin"
    CUSIP = "cusip"
    SEDOL = "sedol"
    FIGI = "figi"
    BLOOMBERG = "bloomberg"
    REUTERS_RIC = "reuters_ric"
    INTERNAL = "internal"


class InstrumentIdentifierRecord(Base):
    __tablename__ = "instrument_identifiers"
    __table_args__ = (
        UniqueConstraint("id_type", "id_value", name="uq_identifier_type_value"),
        Index("ix_sm_identifiers_instrument", "instrument_id"),
        Index("ix_sm_identifiers_type_value", "id_type", "id_value"),
        {"schema": "security_master"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    instrument_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("security_master.instruments.id", ondelete="CASCADE"),
        nullable=False,
    )
    id_type: Mapped[str] = mapped_column(String(32), nullable=False)
    id_value: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
