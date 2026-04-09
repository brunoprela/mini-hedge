"""InvestorKYCRecord — KYC/AML screening status."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class InvestorKYCRecord(Base):
    """KYC/AML screening status — platform-scoped."""

    __tablename__ = "investor_kyc"
    __table_args__ = (
        Index("ix_investor_kyc_investor", "investor_id", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    investor_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    kyc_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    aml_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    sanctions_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pep_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_of_funds_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accredited_investor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_screened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    screening_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    screening_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
