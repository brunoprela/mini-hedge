"""Fund admin service — manages fund lifecycle and provisioning."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.platform.interface import FundDetail, FundPage
from app.modules.platform.models import FundRecord, FundStatus
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

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
        self._fga = fga_client
        self._audit = audit_repo
        self._engine = engine
        self._event_bus = event_bus
        self._auth_service = auth_service

    async def list_funds(self, *, limit: int = 100, offset: int = 0) -> FundPage:
        records, total = await self._fund_repo.get_all_paginated(limit=limit, offset=offset)
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
        actor: RequestContext,
    ) -> FundDetail:
        existing = await self._fund_repo.get_by_slug(slug)
        if existing is not None:
            raise ValidationError("Fund slug already in use")
        record = FundRecord(
            slug=slug,
            name=name,
            status=FundStatus.ACTIVE,
            base_currency=base_currency,
        )
        await self._fund_repo.insert(record)

        # Provision fund infrastructure (schema + Kafka topics)
        if self._engine is not None:
            from app.shared.fund_schema import create_fund_schema

            await create_fund_schema(self._engine, slug)

        if self._event_bus is not None:
            from app.shared.fund_schema import create_fund_kafka_topics
            from app.shared.schema_registry import fund_topic

            create_fund_kafka_topics(self._event_bus, slug)
            # Subscribe audit consumer for the new fund
            self._event_bus.subscribe(
                fund_topic(slug, "trades.executed"),
                self._audit.insert,
            )

        await self._audit.insert_admin_event(
            event_type="admin.fund.created",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=slug,
            payload={"fund_id": record.id, "slug": slug, "name": name},
        )
        return _fund_to_detail(record)

    async def update_fund(
        self,
        fund_id: str,
        *,
        actor: RequestContext,
        **fields: object,
    ) -> FundDetail:
        record = await self._fund_repo.update(fund_id, **fields)
        if record is None:
            raise NotFoundError("Fund", fund_id)
        await self._audit.insert_admin_event(
            event_type="admin.fund.updated",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=record.slug,
            payload={"fund_id": fund_id, "fields": {k: str(v) for k, v in fields.items()}},
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
