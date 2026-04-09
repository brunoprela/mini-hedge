"""Audit log model and PostgreSQL immutability triggers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger
from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


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
