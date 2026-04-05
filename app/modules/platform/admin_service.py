"""Admin service — thin facade that delegates to focused sub-services.

All authorization writes go through OpenFGA. Identity records are managed
in PostgreSQL. Every mutation is audit-logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.platform.access_service import AccessGrantService
from app.modules.platform.fund_service import FundAdminService
from app.modules.platform.operator_service import OperatorAdminService
from app.modules.platform.user_service import UserAdminService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.auth_service import AuthService
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.interface import (
        AuditPage,
        FundAccessGrant,
        FundDetail,
        FundPage,
        OperatorInfo,
        OperatorPage,
        UserInfo,
        UserPage,
    )
    from app.modules.platform.operator_repository import OperatorRepository
    from app.modules.platform.user_repository import UserRepository
    from app.shared.events import EventBus
    from app.shared.fga import FGAClient
    from app.shared.request_context import RequestContext


class AdminService:
    """Admin operations for platform management.

    Delegates to focused sub-services while preserving the original API
    so that ``admin_routes.py`` does not need any changes.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        operator_repo: OperatorRepository,
        fund_repo: FundRepository,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
        engine: AsyncEngine | None = None,
        event_bus: EventBus | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._user_service = UserAdminService(user_repo=user_repo, audit_repo=audit_repo)
        self._operator_service = OperatorAdminService(
            operator_repo=operator_repo, fga_client=fga_client, audit_repo=audit_repo
        )
        self._fund_service = FundAdminService(
            fund_repo=fund_repo,
            fga_client=fga_client,
            audit_repo=audit_repo,
            engine=engine,
            event_bus=event_bus,
            auth_service=auth_service,
        )
        self._access_service = AccessGrantService(
            user_repo=user_repo,
            operator_repo=operator_repo,
            fund_repo=fund_repo,
            fga_client=fga_client,
            audit_repo=audit_repo,
            auth_service=auth_service,
        )

    # ----- Users -----

    async def list_users(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> UserPage:
        return await self._user_service.list_users(limit=limit, offset=offset, session=session)

    async def create_user(
        self,
        *,
        email: str,
        name: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> UserInfo:
        return await self._user_service.create_user(
            email=email, name=name, request_context=request_context, session=session
        )

    async def get_user(self, user_id: str, *, session: AsyncSession | None = None) -> UserInfo:
        return await self._user_service.get_user(user_id, session=session)

    async def update_user(
        self,
        user_id: str,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
        **fields: object,
    ) -> UserInfo:
        return await self._user_service.update_user(
            user_id, request_context=request_context, session=session, **fields
        )

    # ----- Operators -----

    async def list_operators(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> OperatorPage:
        return await self._operator_service.list_operators(
            limit=limit, offset=offset, session=session
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
        return await self._operator_service.create_operator(
            email=email,
            name=name,
            platform_role=platform_role,
            request_context=request_context,
            session=session,
        )

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
        return await self._operator_service.update_operator(
            operator_id,
            request_context=request_context,
            name=name,
            is_active=is_active,
            platform_role=platform_role,
            session=session,
        )

    # ----- Funds -----

    async def list_funds(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> FundPage:
        return await self._fund_service.list_funds(limit=limit, offset=offset, session=session)

    async def create_fund(
        self,
        *,
        slug: str,
        name: str,
        base_currency: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> FundDetail:
        return await self._fund_service.create_fund(
            slug=slug,
            name=name,
            base_currency=base_currency,
            request_context=request_context,
            session=session,
        )

    async def update_fund(
        self,
        fund_id: str,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
        **fields: object,
    ) -> FundDetail:
        return await self._fund_service.update_fund(
            fund_id, request_context=request_context, session=session, **fields
        )

    # ----- Fund access grants -----

    async def list_fund_access(
        self, fund_id: str, *, session: AsyncSession | None = None
    ) -> list[FundAccessGrant]:
        return await self._access_service.list_fund_access(fund_id, session=session)

    async def grant_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> None:
        return await self._access_service.grant_access(
            fund_id,
            user_type=user_type,
            user_id=user_id,
            relation=relation,
            request_context=request_context,
            session=session,
        )

    async def revoke_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> None:
        return await self._access_service.revoke_access(
            fund_id,
            user_type=user_type,
            user_id=user_id,
            relation=relation,
            request_context=request_context,
            session=session,
        )

    # ----- Audit -----

    async def list_audit(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> AuditPage:
        return await self._access_service.list_audit(
            fund_slug=fund_slug, event_type=event_type, limit=limit, offset=offset, session=session
        )
