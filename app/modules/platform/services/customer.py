"""Customer admin service — manages platform customers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.platform.interfaces.customer import (
    CustomerInfo,
    CustomerPage,
    UpdateCustomerRequest,
)
from app.modules.platform.models.customer import CustomerRecord
from app.shared.audit.events import AuditEventType
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.repositories import AuditLogRepository, CustomerRepository
    from app.shared.auth.request_context import RequestContext

logger = structlog.get_logger()


class CustomerAdminService:
    """CRUD operations for platform customers."""

    def __init__(
        self,
        *,
        customer_repo: CustomerRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._customer_repo = customer_repo
        self._audit_repo = audit_repo

    async def list_customers(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> CustomerPage:
        records, total = await self._customer_repo.get_all_paginated(
            limit=limit, offset=offset, session=session
        )
        return CustomerPage(
            items=[_customer_to_info(r) for r in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_customer(
        self,
        *,
        slug: str,
        name: str,
        customer_type: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> CustomerInfo:
        existing = await self._customer_repo.get_by_slug(slug, session=session)
        if existing is not None:
            raise ValidationError("Customer with this slug already exists")
        record = CustomerRecord(slug=slug, name=name, customer_type=customer_type)
        await self._customer_repo.insert(record, session=session)
        await self._audit_repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_CUSTOMER_CREATED,
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={"slug": slug, "name": name, "customer_type": customer_type},
            session=session,
        )
        return _customer_to_info(record)

    async def get_customer(
        self, customer_id: str, *, session: AsyncSession | None = None
    ) -> CustomerInfo:
        record = await self._customer_repo.get_by_id(customer_id, session=session)
        if record is None:
            raise NotFoundError("Customer", customer_id)
        return _customer_to_info(record)

    async def update_customer(
        self,
        customer_id: str,
        updates: UpdateCustomerRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> CustomerInfo:
        record = await self._customer_repo.update(customer_id, updates, session=session)
        if record is None:
            raise NotFoundError("Customer", customer_id)
        await self._audit_repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_CUSTOMER_UPDATED,
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={
                "customer_id": customer_id,
                "changes": updates.model_dump(exclude_none=True),
            },
            session=session,
        )
        return _customer_to_info(record)


def _customer_to_info(r: CustomerRecord) -> CustomerInfo:
    return CustomerInfo(
        id=r.id,
        slug=r.slug,
        name=r.name,
        customer_type=r.customer_type,
        status=r.status,
    )
