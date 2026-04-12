"""Customer model — the organizational tenant between cell and fund.

A customer is either a direct hedge fund (direct_fund) or a fund administrator
(fund_administrator) like Citco or SS&C that services multiple hedge funds.
Every fund belongs to exactly one customer. Every user has a home customer.

See ADR 0010 (cell-based multi-tenant) and ADR 0011 (customer persona and
delegated access) for the full design rationale.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class CustomerType(StrEnum):
    """The two customer personas that drive authorization and routing."""

    DIRECT_FUND = "direct_fund"
    """A hedge fund operating its own desk — the common case."""

    FUND_ADMINISTRATOR = "fund_administrator"
    """A fund admin (Citco, SS&C) that services multiple hedge fund customers."""


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFBOARDED = "offboarded"


class CustomerRecord(Base):
    """Platform-scoped customer — the organizational tenant.

    Hierarchy: Cell → Customer → Fund.
    """

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_platform_customers_slug", "slug", unique=True),
        Index("ix_platform_customers_type", "customer_type"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CustomerType.DIRECT_FUND
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CustomerStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    offboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
