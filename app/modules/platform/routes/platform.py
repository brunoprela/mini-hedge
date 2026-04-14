"""FastAPI routes for the platform module — auth endpoints, fund info."""

import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.core.audit_verifier import AuditIntegrityVerifier, AuditVerificationResult
from app.modules.platform.dependencies import (
    get_api_key_repo,
    get_audit_repo,
    get_audit_verifier,
    get_auth_service,
    get_portfolio_repo,
)
from app.modules.platform.repositories.api_key import APIKeyRepository
from app.modules.platform.interfaces.fund import FundInfo, PortfolioInfo
from app.modules.platform.models.portfolio import PortfolioRecord
from app.modules.platform.repositories import AuditLogRepository, PortfolioRepository
from app.modules.platform.services import AuthService
from app.shared.audit.events import AuditEventType
from app.shared.auth import (
    Permission,
    get_actor_context,
    require_permission,
    require_platform_permission,
    resolve_permissions,
)
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.auth.token_revocation import TokenRevocationService
from app.shared.database import get_db

router = APIRouter(tags=["platform"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AgentTokenRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_name: str
    roles: list[str] = ["viewer"]


class AgentTokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    token_type: str = "bearer"
    actor_type: str
    fund_slug: str
    roles: list[str]


class AuditVerifyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    records_checked: int
    first_broken_link: str | None = None


class CreatePortfolioRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    strategy: str | None = None
    base_currency: str | None = None  # accepted but ignored — currency is fund-level


class RevokeTokenRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    jti: str
    expires_at: datetime


class RevokeTokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "revoked"
    jti: str


class RevokeUserTokensResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "revoked"
    user_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me/funds", response_model=list[FundInfo])
async def list_my_funds(
    request_context: RequestContext = Depends(get_actor_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[FundInfo]:
    """Return all funds the authenticated user has access to.

    Requires authentication only — no specific permission needed.
    This endpoint bootstraps the fund selector before fund context exists.
    """
    return await auth_service.get_user_funds(
        request_context.actor_id, actor_type=request_context.actor_type
    )


@router.post("/auth/agent-token", response_model=AgentTokenResponse)
async def create_agent_token(
    body: AgentTokenRequest,
    request_context: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    auth_service: AuthService = Depends(get_auth_service),
    audit_repo: AuditLogRepository = Depends(get_audit_repo),
    session: AsyncSession = Depends(get_db),
) -> AgentTokenResponse:
    """Issue a JWT for an LLM agent.

    Requires an authenticated user with ``funds:manage`` permission.
    The agent token is scoped to the caller's fund and carries the
    delegating user's ID for audit. The agent cannot be granted more
    permissions than the delegating user holds.
    """
    # Prevent privilege escalation: agent permissions must be a subset
    # of the delegator's permissions.
    agent_permissions = resolve_permissions(frozenset(body.roles))
    if not agent_permissions <= request_context.permissions:
        escalated = sorted(agent_permissions - request_context.permissions)
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delegate permissions you don't hold: {', '.join(escalated)}",
        )

    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required for agent tokens")
    fund_slug = request_context.fund_slug

    agent_id = str(uuid4())
    token = auth_service.issue_agent_token(
        agent_id=agent_id,
        fund_slug=fund_slug,
        fund_id=request_context.fund_id,
        roles=body.roles,
        delegated_by=request_context.actor_id,
    )

    await audit_repo.insert_admin_event(
        event_type=AuditEventType.AUTH_AGENT_TOKEN_CREATED,
        actor_id=request_context.actor_id,
        actor_type=request_context.actor_type.value,
        fund_slug=request_context.fund_slug,
        payload={
            "agent_id": agent_id,
            "agent_name": body.agent_name,
            "roles": body.roles,
        },
        session=session,
    )

    return AgentTokenResponse(
        access_token=token,
        actor_type=ActorType.AGENT,
        fund_slug=fund_slug,
        roles=body.roles,
    )


@router.get("/portfolios", response_model=list[PortfolioInfo])
async def list_portfolios(
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> list[PortfolioInfo]:
    """Return all active portfolios for the authenticated user's fund."""
    if not request_context.fund_id:
        return []
    records = await portfolio_repo.get_by_fund(request_context.fund_id, session=session)
    return [
        PortfolioInfo(
            id=r.id,
            slug=r.slug,
            name=r.name,
            strategy=r.strategy,
            fund_id=r.fund_id,
        )
        for r in records
    ]


@router.post("/portfolios", response_model=PortfolioInfo, status_code=201)
async def create_portfolio(
    body: CreatePortfolioRequest,
    request_context: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> PortfolioInfo:
    """Create a new portfolio within the authenticated user's fund."""
    if not request_context.fund_id:
        raise HTTPException(status_code=400, detail="Fund context required")

    # Generate slug from name: lowercase, replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    if not slug:
        raise HTTPException(status_code=400, detail="Name must contain alphanumeric characters")

    record = PortfolioRecord(
        fund_id=request_context.fund_id,
        slug=slug,
        name=body.name,
        strategy=body.strategy,
    )
    await portfolio_repo.insert(record, session=session)

    return PortfolioInfo(
        id=record.id,
        slug=record.slug,
        name=record.name,
        strategy=record.strategy,
        fund_id=record.fund_id,
    )


@router.get("/audit/verify", response_model=AuditVerifyResponse)
async def verify_audit_integrity(
    limit: int = 10000,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    verifier: AuditIntegrityVerifier = Depends(get_audit_verifier),
    session: AsyncSession = Depends(get_db),
) -> AuditVerifyResponse:
    """Run integrity verification on the audit log hash chain."""
    result: AuditVerificationResult = await verifier.verify(limit=limit, session=session)
    return AuditVerifyResponse(
        is_valid=result.is_valid,
        records_checked=result.records_checked,
        first_broken_link=result.first_broken_link,
    )


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------

import hashlib
import secrets


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    scopes: list[str] = []


class ApiKeyInfo(BaseModel):
    id: str
    name: str
    key_hint: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeyCreateResponse(ApiKeyInfo):
    key: str


@router.get("/api-keys", response_model=list[ApiKeyInfo])
async def list_api_keys(
    request_context: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    api_key_repo: APIKeyRepository = Depends(get_api_key_repo),
    session: AsyncSession = Depends(get_db),
) -> list[ApiKeyInfo]:
    """List API keys for the current fund."""
    from sqlalchemy import select

    from app.modules.platform.models.api_key import APIKeyRecord

    stmt = select(APIKeyRecord).where(
        APIKeyRecord.fund_id == request_context.fund_id,
        APIKeyRecord.is_active.is_(True),
    )
    result = await session.execute(stmt)
    records = list(result.scalars().all())
    return [
        ApiKeyInfo(
            id=r.id,
            name=r.name,
            key_hint=f"...{r.key_hash[-6:]}",
            scopes=r.roles,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    request_context: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    api_key_repo: APIKeyRepository = Depends(get_api_key_repo),
) -> ApiKeyCreateResponse:
    """Create a new API key for the current fund."""
    from app.modules.platform.models.api_key import APIKeyRecord

    raw_key = f"mh_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    record = APIKeyRecord(
        name=body.name,
        key_hash=key_hash,
        actor_type="apikey",
        fund_id=request_context.fund_id,
        roles=body.scopes or ["viewer"],
        is_active=True,
        created_by=request_context.actor_id,
    )
    await api_key_repo.insert(record)
    return ApiKeyCreateResponse(
        id=record.id,
        name=record.name,
        key=raw_key,
        key_hint=f"...{key_hash[-6:]}",
        scopes=record.roles,
        created_at=record.created_at,
    )


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    request_context: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Revoke (soft-delete) an API key."""
    from sqlalchemy import update

    from app.modules.platform.models.api_key import APIKeyRecord

    result = await session.execute(
        update(APIKeyRecord)
        .where(
            APIKeyRecord.id == key_id,
            APIKeyRecord.fund_id == request_context.fund_id,
        )
        .values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Token Revocation
# ---------------------------------------------------------------------------


def _get_token_revocation(request: Request) -> TokenRevocationService:
    service: TokenRevocationService | None = getattr(request.app.state, "token_revocation", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Token revocation service unavailable")
    return service


@router.post("/platform/tokens/revoke", response_model=RevokeTokenResponse)
async def revoke_token(
    body: RevokeTokenRequest,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    revocation: TokenRevocationService = Depends(_get_token_revocation),
    audit_repo: AuditLogRepository = Depends(get_audit_repo),
    session: AsyncSession = Depends(get_db),
) -> RevokeTokenResponse:
    """Revoke a specific token by its JTI. Requires platform admin permission."""
    await revocation.revoke_token(body.jti, body.expires_at)

    await audit_repo.insert_admin_event(
        event_type=AuditEventType.AUTH_TOKEN_REVOKED,
        actor_id=request_context.actor_id,
        actor_type=request_context.actor_type.value,
        fund_slug=request_context.fund_slug,
        payload={"jti": body.jti},
        session=session,
    )

    return RevokeTokenResponse(jti=body.jti)


@router.post(
    "/platform/users/{user_id}/revoke-tokens",
    response_model=RevokeUserTokensResponse,
)
async def revoke_user_tokens(
    user_id: str,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_USERS_WRITE),
    revocation: TokenRevocationService = Depends(_get_token_revocation),
    audit_repo: AuditLogRepository = Depends(get_audit_repo),
    session: AsyncSession = Depends(get_db),
) -> RevokeUserTokensResponse:
    """Revoke all tokens for a user. Requires platform admin permission."""
    await revocation.revoke_user_tokens(user_id)

    await audit_repo.insert_admin_event(
        event_type=AuditEventType.AUTH_USER_TOKENS_REVOKED,
        actor_id=request_context.actor_id,
        actor_type=request_context.actor_type.value,
        fund_slug=request_context.fund_slug,
        payload={"target_user_id": user_id},
        session=session,
    )

    return RevokeUserTokensResponse(user_id=user_id)
