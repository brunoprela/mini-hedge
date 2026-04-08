"""SQLAlchemy models for the platform schema."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


class FundStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFBOARDED = "offboarded"


class FundRecord(Base):
    __tablename__ = "funds"
    __table_args__ = (
        Index("ix_platform_funds_slug", "slug", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=FundStatus.ACTIVE)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    offboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PortfolioRecord(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        Index("ix_platform_portfolios_fund", "fund_id"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    fund_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("platform.funds.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_platform_users_email", "email", unique=True),
        Index("ix_platform_users_keycloak_sub", "keycloak_sub", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    keycloak_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OperatorRecord(Base):
    __tablename__ = "operators"
    __table_args__ = (
        Index("ix_platform_operators_email", "email", unique=True),
        Index("ix_platform_operators_keycloak_sub", "keycloak_sub", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    keycloak_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class APIKeyRecord(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_platform_api_keys_hash", "key_hash", unique=True),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="apikey")
    fund_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.funds.id"),
        nullable=False,
    )
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("platform.users.id"),
        nullable=True,
    )


class AuditLogRecord(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_platform_audit_log_event_type", "event_type"),
        Index("ix_platform_audit_log_fund_slug", "fund_slug"),
        Index("ix_platform_audit_log_created_at", "created_at"),
        Index("ix_platform_audit_log_entry_hash", "entry_hash"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fund_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestorRecord(Base):
    """Platform-scoped investor registry — investors can invest in multiple funds."""

    __tablename__ = "investors"
    __table_args__ = (
        Index("ix_platform_investors_entity_type", "entity_type"),
        Index("ix_platform_investors_active", "is_active"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # individual, institution, fund_of_funds
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# PostgreSQL entities — audit log immutability triggers
# Managed by alembic_utils: autogenerate detects drift vs. live database.
# ---------------------------------------------------------------------------

audit_log_immutable_fn = PGFunction(
    schema="platform",
    signature="audit_log_immutable()",
    definition="""
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is immutable: % operations are not permitted', TG_OP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """,
)

audit_log_no_update = PGTrigger(
    schema="platform",
    signature="audit_log_no_update",
    on_entity="platform.audit_log",
    is_constraint=False,
    definition="""
        BEFORE UPDATE ON platform.audit_log
        FOR EACH ROW
        EXECUTE FUNCTION platform.audit_log_immutable()
    """,
)

audit_log_no_delete = PGTrigger(
    schema="platform",
    signature="audit_log_no_delete",
    on_entity="platform.audit_log",
    is_constraint=False,
    definition="""
        BEFORE DELETE ON platform.audit_log
        FOR EACH ROW
        EXECUTE FUNCTION platform.audit_log_immutable()
    """,
)

audit_log_no_truncate = PGTrigger(
    schema="platform",
    signature="audit_log_no_truncate",
    on_entity="platform.audit_log",
    is_constraint=False,
    definition="""
        BEFORE TRUNCATE ON platform.audit_log
        FOR EACH STATEMENT
        EXECUTE FUNCTION platform.audit_log_immutable()
    """,
)

PLATFORM_ENTITIES = [
    audit_log_immutable_fn,
    audit_log_no_update,
    audit_log_no_delete,
    audit_log_no_truncate,
]
