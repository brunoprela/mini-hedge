"""Operator admin service — manages platform operators and their roles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from openfga_sdk.client.models import ClientTuple

from app.modules.platform.interface import OperatorInfo, OperatorPage
from app.modules.platform.models import OperatorRecord
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.operator_repository import OperatorRepository
    from app.shared.fga import FGAClient
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()

_PLATFORM_ROLES = ["ops_admin", "ops_viewer"]


class OperatorAdminService:
    """CRUD operations for platform operators with FGA role management."""

    def __init__(
        self,
        *,
        operator_repo: OperatorRepository,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._operator_repo = operator_repo
        self._fga_client = fga_client
        self._audit_repo = audit_repo

    async def list_operators(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> OperatorPage:
        records, total = await self._operator_repo.get_all_paginated(
            limit=limit, offset=offset, session=session
        )
        items: list[OperatorInfo] = []
        for r in records:
            roles = await self._fga_client.list_relations(
                user=f"operator:{r.id}",
                object="platform:global",
                relations=_PLATFORM_ROLES,
            )
            role = "ops_admin" if "ops_admin" in roles else (roles[0] if roles else None)
            items.append(_operator_to_info(r, platform_role=role))
        return OperatorPage(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_operator(
        self,
        *,
        email: str,
        name: str,
        platform_role: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> OperatorInfo:
        existing = await self._operator_repo.get_by_email(email, session=session)
        if existing is not None:
            raise ValidationError("Operator with this email already exists")
        record = OperatorRecord(email=email, name=name, is_active=True)
        await self._operator_repo.insert(record, session=session)
        # Grant platform role via FGA
        await self._fga_client.write_tuples(
            [
                ClientTuple(
                    user=f"operator:{record.id}",
                    relation=platform_role,
                    object="platform:global",
                )
            ]
        )
        await self._audit_repo.insert_admin_event(
            event_type="admin.operator.created",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={
                "email": email,
                "name": name,
                "operator_id": record.id,
                "platform_role": platform_role,
            },
            session=session,
        )
        return _operator_to_info(record, platform_role=platform_role)

    async def update_operator(
        self,
        operator_id: str,
        *,
        request_context: RequestContext,
        name: str | None = None,
        is_active: bool | None = None,
        platform_role: str | None = None,
        session: AsyncSession | None = None,
    ) -> OperatorInfo:
        fields: dict[str, object] = {}
        if name is not None:
            fields["name"] = name
        if is_active is not None:
            fields["is_active"] = is_active
        record = (
            await self._operator_repo.update(operator_id, session=session, **fields)
            if fields
            else None
        )
        if record is None:
            record = await self._operator_repo.get_by_id(operator_id, session=session)
        if record is None:
            raise NotFoundError("Operator", operator_id)

        # Update platform role if requested
        if platform_role is not None:
            # Remove old roles, add new one
            old_roles = await self._fga_client.list_relations(
                user=f"operator:{operator_id}",
                object="platform:global",
                relations=_PLATFORM_ROLES,
            )
            if old_roles:
                await self._fga_client.delete_tuples(
                    [
                        ClientTuple(
                            user=f"operator:{operator_id}",
                            relation=r,
                            object="platform:global",
                        )
                        for r in old_roles
                    ]
                )
            await self._fga_client.write_tuples(
                [
                    ClientTuple(
                        user=f"operator:{operator_id}",
                        relation=platform_role,
                        object="platform:global",
                    )
                ]
            )

        await self._audit_repo.insert_admin_event(
            event_type="admin.operator.updated",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={"operator_id": operator_id, "fields": {k: str(v) for k, v in fields.items()}},
            session=session,
        )

        # Resolve current role for response
        roles = await self._fga_client.list_relations(
            user=f"operator:{operator_id}",
            object="platform:global",
            relations=_PLATFORM_ROLES,
        )
        role = "ops_admin" if "ops_admin" in roles else (roles[0] if roles else None)
        return _operator_to_info(record, platform_role=role)


def _operator_to_info(r: OperatorRecord, *, platform_role: str | None = None) -> OperatorInfo:
    return OperatorInfo(
        id=r.id,
        email=r.email,
        name=r.name,
        is_active=r.is_active,
        platform_role=platform_role,
    )
