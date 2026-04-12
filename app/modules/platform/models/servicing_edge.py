"""Servicing edge — fund administrator → serviced customer relationship.

A servicing edge grants a fund_administrator customer scoped access to a
direct_fund customer's resources. Users from the admin customer can act on
the client customer's funds, but only with the intersection of:
  1. Their home customer grants (what they can do at their employer)
  2. The edge's scoped_roles (what the client customer has delegated)

See ADR 0011 (customer persona and delegated access) for the full design.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class ServicingEdgeStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ServicingEdgeRecord(Base):
    """Directional link: admin_customer services client_customer.

    The scoped_roles array limits what users from the admin customer
    can do when acting on the client customer's funds. Temporal bounds
    allow onboarding/offboarding without deleting the edge.
    """

    __tablename__ = "servicing_edges"
    __table_args__ = (
        Index(
            "ix_platform_servicing_edges_admin_client",
            "admin_customer_id",
            "client_customer_id",
            unique=True,
        ),
        Index("ix_platform_servicing_edges_client", "client_customer_id"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    admin_customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.customers.id"),
        nullable=False,
    )
    client_customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.customers.id"),
        nullable=False,
    )
    # Roles the admin customer's users may assume on the client's funds.
    # Empty array means no access (edge exists but is effectively disabled).
    scoped_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), nullable=False, server_default=text("'{}'::text[]")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ServicingEdgeStatus.ACTIVE
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
