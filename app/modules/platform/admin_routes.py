"""Admin API routes — platform operator endpoints for managing users, funds, and access."""

from fastapi import APIRouter, Depends

from app.modules.platform.admin_service import AdminService
from app.modules.platform.dependencies import get_admin_service
from app.modules.platform.interface import (
    AccessGrantRequest,
    AccessRevokeRequest,
    AuditPage,
    CreateFundRequest,
    CreateOperatorRequest,
    CreateUserRequest,
    FundAccessGrant,
    FundDetail,
    OperatorInfo,
    UpdateFundRequest,
    UpdateOperatorRequest,
    UpdateUserRequest,
    UserInfo,
)
from app.shared.auth import Permission, require_platform_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserInfo])
async def list_users(
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_READ),
    svc: AdminService = Depends(get_admin_service),
) -> list[UserInfo]:
    return await svc.list_users()


@router.post("/users", response_model=UserInfo, status_code=201)
async def create_user(
    body: CreateUserRequest,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    svc: AdminService = Depends(get_admin_service),
) -> UserInfo:
    return await svc.create_user(email=body.email, name=body.name, actor=ctx)


@router.get("/users/{user_id}", response_model=UserInfo)
async def get_user(
    user_id: str,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_READ),
    svc: AdminService = Depends(get_admin_service),
) -> UserInfo:
    return await svc.get_user(user_id)


@router.patch("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    svc: AdminService = Depends(get_admin_service),
) -> UserInfo:
    fields = body.model_dump(exclude_none=True)
    return await svc.update_user(user_id, actor=ctx, **fields)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


@router.get("/operators", response_model=list[OperatorInfo])
async def list_operators(
    ctx: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_READ
    ),
    svc: AdminService = Depends(get_admin_service),
) -> list[OperatorInfo]:
    return await svc.list_operators()


@router.post("/operators", response_model=OperatorInfo, status_code=201)
async def create_operator(
    body: CreateOperatorRequest,
    ctx: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_WRITE
    ),
    svc: AdminService = Depends(get_admin_service),
) -> OperatorInfo:
    return await svc.create_operator(
        email=body.email, name=body.name,
        platform_role=body.platform_role, actor=ctx,
    )


@router.patch("/operators/{operator_id}", response_model=OperatorInfo)
async def update_operator(
    operator_id: str,
    body: UpdateOperatorRequest,
    ctx: RequestContext = require_platform_permission(
        Permission.PLATFORM_OPERATORS_WRITE
    ),
    svc: AdminService = Depends(get_admin_service),
) -> OperatorInfo:
    return await svc.update_operator(
        operator_id, actor=ctx,
        name=body.name, is_active=body.is_active,
        platform_role=body.platform_role,
    )


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------


@router.get("/funds", response_model=list[FundDetail])
async def list_funds(
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_READ),
    svc: AdminService = Depends(get_admin_service),
) -> list[FundDetail]:
    return await svc.list_funds()


@router.post("/funds", response_model=FundDetail, status_code=201)
async def create_fund(
    body: CreateFundRequest,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_WRITE),
    svc: AdminService = Depends(get_admin_service),
) -> FundDetail:
    return await svc.create_fund(
        slug=body.slug, name=body.name,
        base_currency=body.base_currency, actor=ctx,
    )


@router.patch("/funds/{fund_id}", response_model=FundDetail)
async def update_fund(
    fund_id: str,
    body: UpdateFundRequest,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_FUNDS_WRITE),
    svc: AdminService = Depends(get_admin_service),
) -> FundDetail:
    fields = body.model_dump(exclude_none=True)
    return await svc.update_fund(fund_id, actor=ctx, **fields)


# ---------------------------------------------------------------------------
# Fund access
# ---------------------------------------------------------------------------


@router.get("/funds/{fund_id}/access", response_model=list[FundAccessGrant])
async def list_fund_access(
    fund_id: str,
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_ACCESS_READ),
    svc: AdminService = Depends(get_admin_service),
) -> list[FundAccessGrant]:
    return await svc.list_fund_access(fund_id)


@router.post("/funds/{fund_id}/access", status_code=204)
async def grant_access(
    fund_id: str,
    body: AccessGrantRequest,
    ctx: RequestContext = require_platform_permission(
        Permission.PLATFORM_ACCESS_WRITE
    ),
    svc: AdminService = Depends(get_admin_service),
) -> None:
    await svc.grant_access(
        fund_id, user_type=body.user_type,
        user_id=body.user_id, relation=body.relation, actor=ctx,
    )


@router.delete("/funds/{fund_id}/access", status_code=204)
async def revoke_access(
    fund_id: str,
    body: AccessRevokeRequest,
    ctx: RequestContext = require_platform_permission(
        Permission.PLATFORM_ACCESS_WRITE
    ),
    svc: AdminService = Depends(get_admin_service),
) -> None:
    await svc.revoke_access(
        fund_id, user_type=body.user_type,
        user_id=body.user_id, relation=body.relation, actor=ctx,
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
    ctx: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    svc: AdminService = Depends(get_admin_service),
) -> AuditPage:
    return await svc.list_audit(
        fund_slug=fund_slug, event_type=event_type,
        limit=limit, offset=offset,
    )
