"""Admin API routes — platform operator endpoints for managing users, funds, and access."""


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.dependencies import get_admin_service
from app.modules.platform.interfaces.access import (
    AccessGrantRequest,
    AccessRevokeRequest,
    FundAccessGrant,
)
from app.modules.platform.interfaces.audit import AuditPage
from app.modules.platform.interfaces.customer import (
    CreateCustomerRequest,
    CustomerInfo,
    CustomerPage,
    UpdateCustomerRequest,
)
from app.modules.platform.interfaces.servicing_edge import (
    CreateServicingEdgeRequest,
    ServicingEdgeInfo,
    UpdateScopedRolesRequest,
)
from app.modules.platform.interfaces.fund import (
    CreateFundRequest,
    FundDetail,
    FundPage,
    UpdateFundRequest,
)
from app.modules.platform.interfaces.operator import (
    CreateOperatorRequest,
    OperatorInfo,
    OperatorPage,
    UpdateOperatorRequest,
)
from app.modules.platform.interfaces.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserPage,
)
from app.modules.platform.services import AdminService
from app.shared.auth import Permission, require_platform_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db, get_read_db

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=UserPage)
async def list_users(
    limit: int = 100,
    offset: int = 0,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> UserPage:
    return await admin_service.list_users(limit=limit, offset=offset, session=session)


@router.post("/users", response_model=UserInfo, status_code=201)
async def create_user(
    body: CreateUserRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> UserInfo:
    return await admin_service.create_user(
        email=body.email, name=body.name, request_context=request_context, session=session
    )


@router.get("/users/{user_id}", response_model=UserInfo)
async def get_user(
    user_id: str,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> UserInfo:
    return await admin_service.get_user(user_id, session=session)


@router.patch("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> UserInfo:
    return await admin_service.update_user(
        user_id, body, request_context=request_context, session=session
    )


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


@router.get("/operators", response_model=OperatorPage)
async def list_operators(
    limit: int = 100,
    offset: int = 0,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_READ
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> OperatorPage:
    return await admin_service.list_operators(limit=limit, offset=offset, session=session)


@router.post("/operators", response_model=OperatorInfo, status_code=201)
async def create_operator(
    body: CreateOperatorRequest,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_WRITE
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> OperatorInfo:
    return await admin_service.create_operator(
        email=body.email,
        name=body.name,
        platform_role=body.platform_role,
        request_context=request_context,
        session=session,
    )


@router.patch("/operators/{operator_id}", response_model=OperatorInfo)
async def update_operator(
    operator_id: str,
    body: UpdateOperatorRequest,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_WRITE
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> OperatorInfo:
    return await admin_service.update_operator(
        operator_id, body, request_context=request_context, session=session
    )


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


@router.get("/customers", response_model=CustomerPage)
async def list_customers(
    limit: int = 100,
    offset: int = 0,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_CUSTOMERS_READ
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> CustomerPage:
    return await admin_service.list_customers(limit=limit, offset=offset, session=session)


@router.post("/customers", response_model=CustomerInfo, status_code=201)
async def create_customer(
    body: CreateCustomerRequest,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_CUSTOMERS_WRITE
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> CustomerInfo:
    return await admin_service.create_customer(
        slug=body.slug,
        name=body.name,
        customer_type=body.customer_type,
        request_context=request_context,
        session=session,
    )


@router.get("/customers/{customer_id}", response_model=CustomerInfo)
async def get_customer(
    customer_id: str,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_CUSTOMERS_READ
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> CustomerInfo:
    return await admin_service.get_customer(customer_id, session=session)


@router.patch("/customers/{customer_id}", response_model=CustomerInfo)
async def update_customer(
    customer_id: str,
    body: UpdateCustomerRequest,
    request_context: RequestContext = require_platform_permission(
        Permission.PLATFORM_CUSTOMERS_WRITE
    ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> CustomerInfo:
    return await admin_service.update_customer(
        customer_id, body, request_context=request_context, session=session
    )


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------


@router.get("/funds", response_model=FundPage)
async def list_funds(
    limit: int = 100,
    offset: int = 0,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> FundPage:
    return await admin_service.list_funds(limit=limit, offset=offset, session=session)


@router.post("/funds", response_model=FundDetail, status_code=201)
async def create_fund(
    body: CreateFundRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> FundDetail:
    return await admin_service.create_fund(
        slug=body.slug,
        name=body.name,
        base_currency=body.base_currency,
        request_context=request_context,
        session=session,
    )


@router.patch("/funds/{fund_id}", response_model=FundDetail)
async def update_fund(
    fund_id: str,
    body: UpdateFundRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> FundDetail:
    return await admin_service.update_fund(
        fund_id, body, request_context=request_context, session=session
    )


# ---------------------------------------------------------------------------
# Fund access
# ---------------------------------------------------------------------------


@router.get("/funds/{fund_id}/access", response_model=list[FundAccessGrant])
async def list_fund_access(
    fund_id: str,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_ACCESS_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FundAccessGrant]:
    return await admin_service.list_fund_access(fund_id, session=session)


@router.post("/funds/{fund_id}/access", status_code=204)
async def grant_access(
    fund_id: str,
    body: AccessGrantRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_ACCESS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    await admin_service.grant_access(
        fund_id,
        user_type=body.user_type,
        user_id=body.user_id,
        relation=body.relation,
        request_context=request_context,
        session=session,
    )


@router.delete("/funds/{fund_id}/access", status_code=204)
async def revoke_access(
    fund_id: str,
    body: AccessRevokeRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_ACCESS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    await admin_service.revoke_access(
        fund_id,
        user_type=body.user_type,
        user_id=body.user_id,
        relation=body.relation,
        request_context=request_context,
        session=session,
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=AuditPage)
async def list_audit(
    fund_slug: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> AuditPage:
    return await admin_service.list_audit(
        fund_slug=fund_slug,
        event_type=event_type,
        limit=limit,
        offset=offset,
        session=session,
    )


# ---------------------------------------------------------------------------
# Servicing Edges
# ---------------------------------------------------------------------------


@router.post("/servicing-edges", response_model=ServicingEdgeInfo, status_code=201)
async def create_servicing_edge(
    body: CreateServicingEdgeRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_CUSTOMERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> ServicingEdgeInfo:
    record = await admin_service.create_servicing_edge(
        admin_customer_id=body.admin_customer_id,
        client_customer_id=body.client_customer_id,
        scoped_roles=body.scoped_roles,
        session=session,
    )
    return ServicingEdgeInfo.model_validate(record)


@router.get("/servicing-edges", response_model=list[ServicingEdgeInfo])
async def list_servicing_edges(
    admin_customer_id: str | None = None,
    client_customer_id: str | None = None,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_CUSTOMERS_READ),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[ServicingEdgeInfo]:
    edges = await admin_service.list_servicing_edges(
        admin_customer_id=admin_customer_id,
        client_customer_id=client_customer_id,
        session=session,
    )
    return [ServicingEdgeInfo.model_validate(e) for e in edges]


@router.patch("/servicing-edges/{edge_id}/roles", response_model=ServicingEdgeInfo)
async def update_edge_roles(
    edge_id: str,
    body: UpdateScopedRolesRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_CUSTOMERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> ServicingEdgeInfo:
    record = await admin_service.update_servicing_edge_roles(
        edge_id=edge_id,
        scoped_roles=body.scoped_roles,
        session=session,
    )
    return ServicingEdgeInfo.model_validate(record)


@router.post("/servicing-edges/{edge_id}/suspend", response_model=ServicingEdgeInfo)
async def suspend_edge(
    edge_id: str,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_CUSTOMERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> ServicingEdgeInfo:
    record = await admin_service.suspend_servicing_edge(edge_id=edge_id, session=session)
    return ServicingEdgeInfo.model_validate(record)


@router.post("/servicing-edges/{edge_id}/terminate", response_model=ServicingEdgeInfo)
async def terminate_edge(
    edge_id: str,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_CUSTOMERS_WRITE),
    admin_service: AdminService = Depends(get_admin_service),
    session: AsyncSession = Depends(get_db),
) -> ServicingEdgeInfo:
    record = await admin_service.terminate_servicing_edge(edge_id=edge_id, session=session)
    return ServicingEdgeInfo.model_validate(record)
