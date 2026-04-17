"""Protocol for audit log persistence used by shared audit services.

Shared audit components (bridge, CDC consumer, archival service) need to
persist and query audit records but must not depend on any concrete
``app.modules.*`` implementation.  This module defines the minimal
structural interface the shared layer relies on; the concrete
``AuditLogRepository`` in ``app.modules.platform.repositories.audit``
satisfies it structurally and is injected at wiring time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.shared.events import BaseEvent


class AuditLogRecordLike(Protocol):
    """Structural view of an audit log record needed by shared consumers."""

    event_id: str
    event_type: str
    actor_id: str | None
    actor_type: str | None
    fund_slug: str | None
    payload: dict[str, Any]


class AuditLogRepositoryProtocol(Protocol):
    """Structural interface for audit log persistence.

    Any repository that exposes these methods can be injected into
    :class:`~app.shared.audit.bridge.AuditBridge`,
    :class:`~app.shared.audit.cdc_consumer.CdcAuditConsumer`,
    :class:`~app.shared.audit.archival_service.ArchivalService`, and
    :func:`~app.shared.stores.immudb_verifier.verify_audit_batch`
    without the shared layer importing from ``app.modules``.
    """

    async def insert(self, event: BaseEvent) -> None:
        """Persist a domain event to the audit log (idempotent)."""
        ...

    async def insert_cdc_event(
        self,
        *,
        event_type: str,
        actor_id: str,
        actor_type: str,
        fund_slug: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Persist a raw CDC (change-data-capture) event to the audit log."""
        ...

    async def query(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogRecordLike], int]:
        """Return ``(records, total_count)`` for the given filters."""
        ...

    async def get_records_for_period(
        self,
        *,
        start: datetime,
        end: datetime,
        fund_slug: str | None = None,
        batch_size: int = 5000,
    ) -> list[dict[str, Any]]:
        """Fetch audit records in ``[start, end)`` as plain dicts for archival."""
        ...

    async def count_for_period(
        self,
        *,
        start: datetime,
        end: datetime,
        fund_slug: str | None = None,
    ) -> int:
        """Count audit records in ``[start, end)`` optionally scoped to a fund."""
        ...


class FundLike(Protocol):
    """Structural view of a fund record — only ``slug`` is consumed by archival."""

    slug: str


class FundListerProtocol(Protocol):
    """Minimal fund repository surface used by the archival service."""

    async def list_active(self) -> list[FundLike]:
        """Return all currently active funds."""
        ...
