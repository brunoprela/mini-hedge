"""Fund admin service — manages fund lifecycle and provisioning."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.platform.interface import FundDetail, FundPage, UpdateFundRequest
from app.modules.platform.models import FundRecord, FundStatus
from app.shared.audit_events import AuditEventType
from app.shared.errors import NotFoundError, ValidationError
from app.shared.fund_schema import create_fund_kafka_topics, create_fund_schema
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.auth_service import AuthService
    from app.modules.platform.fund_repository import FundRepository
    from app.shared.events import EventBus
    from app.shared.fga import FGAClient
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()


class FundAdminService:
    """CRUD operations for funds with infrastructure provisioning."""

    def __init__(
        self,
        *,
        fund_repo: FundRepository,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
        engine: AsyncEngine | None = None,
        event_bus: EventBus | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._fund_repo = fund_repo
        self._fga_client = fga_client
        self._audit_repo = audit_repo
        self._engine = engine
        self._event_bus = event_bus
        self._auth_service = auth_service
        self._on_fund_created_hooks: list[object] = []  # Callable[[str], Awaitable[None]]

    def register_on_fund_created(self, hook: object) -> None:
        """Register a callback invoked with the fund slug after creation."""
        self._on_fund_created_hooks.append(hook)

    async def list_funds(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> FundPage:
        records, total = await self._fund_repo.get_all_paginated(
            limit=limit, offset=offset, session=session
        )
        return FundPage(
            items=[_fund_to_detail(r) for r in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_fund(
        self,
        *,
        slug: str,
        name: str,
        base_currency: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> FundDetail:
        existing = await self._fund_repo.get_by_slug(slug, session=session)
        if existing is not None:
            raise ValidationError("Fund slug already in use")
        record = FundRecord(
            slug=slug,
            name=name,
            status=FundStatus.ACTIVE,
            base_currency=base_currency,
        )
        await self._fund_repo.insert(record, session=session)

        # Provision fund infrastructure (schema + Kafka topics)
        if self._engine is not None:
            await create_fund_schema(self._engine, slug)

        if self._event_bus is not None:
            await create_fund_kafka_topics(self._event_bus, slug)
            # Subscribe audit consumer for the new fund
            self._event_bus.subscribe(
                fund_topic(slug, "trades.executed"),
                self._audit_repo.insert,
            )

        # Notify modules that need per-fund subscriptions (positions, etc.)
        for hook in self._on_fund_created_hooks:
            try:
                await hook(slug)  # type: ignore[misc]
            except Exception:
                logger.exception("on_fund_created_hook_failed", fund_slug=slug)

        await self._audit_repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_FUND_CREATED,
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            fund_slug=slug,
            payload={"fund_id": record.id, "slug": slug, "name": name},
            session=session,
        )
        return _fund_to_detail(record)

    async def update_fund(
        self,
        fund_id: str,
        updates: UpdateFundRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> FundDetail:
        record = await self._fund_repo.update(fund_id, updates, session=session)
        if record is None:
            raise NotFoundError("Fund", fund_id)
        await self._audit_repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_FUND_UPDATED,
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            fund_slug=record.slug,
            payload={"fund_id": fund_id, "changes": updates.model_dump(exclude_none=True)},
            session=session,
        )
        return _fund_to_detail(record)


def _fund_to_detail(r: FundRecord) -> FundDetail:
    return FundDetail(
        id=r.id,
        slug=r.slug,
        name=r.name,
        status=r.status,
        base_currency=r.base_currency,
    )
