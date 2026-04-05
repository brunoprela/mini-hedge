"""User admin service — manages platform users."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.platform.interface import UserInfo, UserPage
from app.modules.platform.models import UserRecord
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.user_repository import UserRepository
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()


class UserAdminService:
    """CRUD operations for platform users."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    async def list_users(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> UserPage:
        records, total = await self._user_repo.get_all_paginated(
            limit=limit, offset=offset, session=session
        )
        return UserPage(
            items=[_user_to_info(r) for r in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_user(
        self,
        *,
        email: str,
        name: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> UserInfo:
        existing = await self._user_repo.get_by_email(email, session=session)
        if existing is not None:
            raise ValidationError("User with this email already exists")
        record = UserRecord(email=email, name=name, is_active=True)
        await self._user_repo.insert(record, session=session)
        await self._audit_repo.insert_admin_event(
            event_type="admin.user.created",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={"email": email, "name": name, "user_id": record.id},
            session=session,
        )
        return _user_to_info(record)

    async def get_user(self, user_id: str, *, session: AsyncSession | None = None) -> UserInfo:
        record = await self._user_repo.get_by_id(user_id, session=session)
        if record is None:
            raise NotFoundError("User", user_id)
        return _user_to_info(record)

    async def update_user(
        self,
        user_id: str,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
        **fields: object,
    ) -> UserInfo:
        record = await self._user_repo.update(user_id, session=session, **fields)
        if record is None:
            raise NotFoundError("User", user_id)
        await self._audit_repo.insert_admin_event(
            event_type="admin.user.updated",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            payload={"user_id": user_id, "fields": {k: str(v) for k, v in fields.items()}},
            session=session,
        )
        return _user_to_info(record)


def _user_to_info(r: UserRecord) -> UserInfo:
    return UserInfo(id=r.id, email=r.email, name=r.name, is_active=r.is_active)
