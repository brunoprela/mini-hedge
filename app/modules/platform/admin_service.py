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
    from sqlalchemy.ext.asyncio import AsyncEngine

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
        self._users = UserAdminService(user_repo=user_repo, audit_repo=audit_repo)
        self._operators = OperatorAdminService(
            operator_repo=operator_repo, fga_client=fga_client, audit_repo=audit_repo
        )
        self._funds = FundAdminService(
            fund_repo=fund_repo,
            fga_client=fga_client,
            audit_repo=audit_repo,
            engine=engine,
            event_bus=event_bus,
            auth_service=auth_service,
        )
        self._access = AccessGrantService(
            user_repo=user_repo,
            operator_repo=operator_repo,
            fund_repo=fund_repo,
            fga_client=fga_client,
            audit_repo=audit_repo,
            auth_service=auth_service,
        )

    # ----- Users -----

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> UserPage:
        return await self._users.list_users(limit=limit, offset=offset)

    async def create_user(self, *, email: str, name: str, actor: RequestContext) -> UserInfo:
        return await self._users.create_user(email=email, name=name, actor=actor)

    async def get_user(self, user_id: str) -> UserInfo:
        return await self._users.get_user(user_id)

    async def update_user(
        self,
        user_id: str,
        *,
        actor: RequestContext,
        **fields: object,
    ) -> UserInfo:
        return await self._users.update_user(user_id, actor=actor, **fields)

    # ----- Operators -----

    async def list_operators(self, *, limit: int = 100, offset: int = 0) -> OperatorPage:
        return await self._operators.list_operators(limit=limit, offset=offset)

    async def create_operator(
        self,
        *,
        email: str,
        name: str,
        platform_role: str,
        actor: RequestContext,
    ) -> OperatorInfo:
        return await self._operators.create_operator(
            email=email, name=name, platform_role=platform_role, actor=actor
        )

    async def update_operator(
        self,
        operator_id: str,
        *,
        actor: RequestContext,
        name: str | None = None,
        is_active: bool | None = None,
        platform_role: str | None = None,
    ) -> OperatorInfo:
        return await self._operators.update_operator(
            operator_id, actor=actor, name=name, is_active=is_active, platform_role=platform_role
        )

    # ----- Funds -----

    async def list_funds(self, *, limit: int = 100, offset: int = 0) -> FundPage:
        return await self._funds.list_funds(limit=limit, offset=offset)

    async def create_fund(
        self,
        *,
        slug: str,
        name: str,
        base_currency: str,
        actor: RequestContext,
    ) -> FundDetail:
        return await self._funds.create_fund(
            slug=slug, name=name, base_currency=base_currency, actor=actor
        )

    async def update_fund(
        self,
        fund_id: str,
        *,
        actor: RequestContext,
        **fields: object,
    ) -> FundDetail:
        return await self._funds.update_fund(fund_id, actor=actor, **fields)

    # ----- Fund access grants -----

    async def list_fund_access(self, fund_id: str) -> list[FundAccessGrant]:
        return await self._access.list_fund_access(fund_id)

    async def grant_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        actor: RequestContext,
    ) -> None:
        return await self._access.grant_access(
            fund_id, user_type=user_type, user_id=user_id, relation=relation, actor=actor
        )

    async def revoke_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        actor: RequestContext,
    ) -> None:
        return await self._access.revoke_access(
            fund_id, user_type=user_type, user_id=user_id, relation=relation, actor=actor
        )

    # ----- Audit -----

    async def list_audit(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditPage:
        return await self._access.list_audit(
            fund_slug=fund_slug, event_type=event_type, limit=limit, offset=offset
        )
