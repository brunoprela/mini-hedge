"""FastAPI routes for the platform module — auth endpoints, fund info."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.auth_service import AuthService
from app.modules.platform.dependencies import get_audit_repo, get_auth_service, get_portfolio_repo
from app.modules.platform.interface import FundInfo, PortfolioInfo
from app.modules.platform.portfolio_repository import PortfolioRepository
from app.shared.audit_events import AuditEventType
from app.shared.auth import (
    Permission,
    get_actor_context,
    require_permission,
    resolve_permissions,
)
from app.shared.database import get_db
from app.shared.request_context import ActorType, RequestContext

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
    return await auth_service.get_user_funds(request_context.actor_id)


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

    agent_id = str(uuid4())
    token = auth_service.issue_agent_token(
        agent_id=agent_id,
        fund_slug=request_context.fund_slug,
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
        fund_slug=request_context.fund_slug,
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
