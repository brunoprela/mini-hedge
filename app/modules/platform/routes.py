"""FastAPI routes for the platform module — auth endpoints, fund info."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.platform.auth_service import AuthService
from app.modules.platform.dependencies import get_auth_service, get_portfolio_repo
from app.modules.platform.interface import FundInfo, PortfolioInfo
from app.modules.platform.portfolio_repository import PortfolioRepository
from app.shared.auth import Permission, get_actor_context, require_permission, resolve_permissions
from app.shared.request_context import ActorType, RequestContext

router = APIRouter(tags=["platform"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AgentTokenRequest(BaseModel):
    agent_name: str
    roles: list[str] = ["viewer"]


class AgentTokenResponse(BaseModel):
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
    ctx: RequestContext = Depends(get_actor_context),
    auth: AuthService = Depends(get_auth_service),
) -> list[FundInfo]:
    """Return all funds the authenticated user has access to.

    Requires authentication only — no specific permission needed.
    This endpoint bootstraps the fund selector before fund context exists.
    """
    return await auth.get_user_funds(ctx.actor_id)


@router.post("/auth/agent-token", response_model=AgentTokenResponse)
async def create_agent_token(
    body: AgentTokenRequest,
    ctx: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    auth: AuthService = Depends(get_auth_service),
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
    if not agent_permissions <= ctx.permissions:
        escalated = sorted(agent_permissions - ctx.permissions)
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delegate permissions you don't hold: {', '.join(escalated)}",
        )

    agent_id = str(uuid4())
    token = auth.issue_agent_token(
        agent_id=agent_id,
        fund_slug=ctx.fund_slug,
        fund_id=ctx.fund_id,
        roles=body.roles,
        delegated_by=ctx.actor_id,
    )

    return AgentTokenResponse(
        access_token=token,
        actor_type=ActorType.AGENT,
        fund_slug=ctx.fund_slug,
        roles=body.roles,
    )


@router.get("/portfolios", response_model=list[PortfolioInfo])
async def list_portfolios(
    ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
) -> list[PortfolioInfo]:
    """Return all active portfolios for the authenticated user's fund."""
    if not ctx.fund_id:
        return []
    records = await repo.get_by_fund(ctx.fund_id)
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
