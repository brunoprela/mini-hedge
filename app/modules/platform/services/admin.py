"""Admin service — thin facade that delegates to focused sub-services.

All authorization writes go through OpenFGA. Identity records are managed
in PostgreSQL. Every mutation is audit-logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.platform.services.access import AccessGrantService
from app.modules.platform.services.customer import CustomerAdminService
from app.modules.platform.services.fund import FundAdminService
from app.modules.platform.services.operator import OperatorAdminService
from app.modules.platform.services.user import UserAdminService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.modules.platform.interfaces.access import FundAccessGrant
    from app.modules.platform.interfaces.audit import AuditPage
    from app.modules.platform.interfaces.customer import (
        CustomerInfo,
        CustomerPage,
        UpdateCustomerRequest,
    )
    from app.modules.platform.interfaces.fund import FundDetail, FundPage, UpdateFundRequest
    from app.modules.platform.interfaces.operator import (
        OperatorInfo,
        OperatorPage,
        UpdateOperatorRequest,
    )
    from app.modules.platform.interfaces.user import UpdateUserRequest, UserInfo, UserPage
    from app.modules.platform.models.servicing_edge import ServicingEdgeRecord
    from app.modules.platform.repositories import (
        AuditLogRepository,
        CustomerRepository,
        FundRepository,
        OperatorRepository,
        UserRepository,
    )
    from app.modules.platform.repositories.servicing_edge import ServicingEdgeRepository
    from app.modules.platform.services.auth import AuthService
    from app.shared.auth.request_context import RequestContext
    from app.shared.events import EventBus
    from app.shared.fga import FGAClient


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
        customer_repo: CustomerRepository | None = None,
        servicing_edge_repo: ServicingEdgeRepository | None = None,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
        engine: AsyncEngine | None = None,
        event_bus: EventBus | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._user_service = UserAdminService(user_repo=user_repo, audit_repo=audit_repo)
        self._customer_service = (
            CustomerAdminService(customer_repo=customer_repo, audit_repo=audit_repo)
            if customer_repo is not None
            else None
        )
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
        self._servicing_edge_repo = servicing_edge_repo
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
        updates: UpdateUserRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> UserInfo:
        return await self._user_service.update_user(
            user_id, updates, request_context=request_context, session=session
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
        updates: UpdateOperatorRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> OperatorInfo:
        return await self._operator_service.update_operator(
            operator_id, updates, request_context=request_context, session=session
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
        updates: UpdateFundRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> FundDetail:
        return await self._fund_service.update_fund(
            fund_id, updates, request_context=request_context, session=session
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

    # ----- Customers -----

    async def list_customers(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> CustomerPage:
        assert self._customer_service is not None
        return await self._customer_service.list_customers(
            limit=limit, offset=offset, session=session
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
        assert self._customer_service is not None
        return await self._customer_service.create_customer(
            slug=slug,
            name=name,
            customer_type=customer_type,
            request_context=request_context,
            session=session,
        )

    async def get_customer(
        self, customer_id: str, *, session: AsyncSession | None = None
    ) -> CustomerInfo:
        assert self._customer_service is not None
        return await self._customer_service.get_customer(customer_id, session=session)

    async def update_customer(
        self,
        customer_id: str,
        updates: UpdateCustomerRequest,
        *,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> CustomerInfo:
        assert self._customer_service is not None
        return await self._customer_service.update_customer(
            customer_id, updates, request_context=request_context, session=session
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

    # ----- Servicing Edges -----

    async def create_servicing_edge(
        self,
        *,
        admin_customer_id: str,
        client_customer_id: str,
        scoped_roles: list[str],
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord:
        from app.modules.platform.models.servicing_edge import ServicingEdgeRecord as EdgeRecord

        assert self._servicing_edge_repo is not None
        record = EdgeRecord(
            admin_customer_id=admin_customer_id,
            client_customer_id=client_customer_id,
            scoped_roles=scoped_roles,
        )
        await self._servicing_edge_repo.insert(record, session=session)
        return record

    async def list_servicing_edges(
        self,
        *,
        admin_customer_id: str | None = None,
        client_customer_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[ServicingEdgeRecord]:
        assert self._servicing_edge_repo is not None
        if admin_customer_id:
            return await self._servicing_edge_repo.get_client_customers(
                admin_customer_id, session=session
            )
        if client_customer_id:
            return await self._servicing_edge_repo.get_admin_customers(
                client_customer_id, session=session
            )
        return []

    async def update_servicing_edge_roles(
        self,
        edge_id: str,
        scoped_roles: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord:
        assert self._servicing_edge_repo is not None
        record = await self._servicing_edge_repo.update_scoped_roles(
            edge_id, scoped_roles, session=session
        )
        if record is None:
            from app.shared.errors import NotFoundError

            raise NotFoundError(f"Servicing edge {edge_id} not found")
        return record

    async def suspend_servicing_edge(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord:
        assert self._servicing_edge_repo is not None
        record = await self._servicing_edge_repo.suspend(edge_id, session=session)
        if record is None:
            from app.shared.errors import NotFoundError

            raise NotFoundError(f"Servicing edge {edge_id} not found")
        return record

    async def terminate_servicing_edge(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord:
        assert self._servicing_edge_repo is not None
        record = await self._servicing_edge_repo.terminate(edge_id, session=session)
        if record is None:
            from app.shared.errors import NotFoundError

            raise NotFoundError(f"Servicing edge {edge_id} not found")
        return record
