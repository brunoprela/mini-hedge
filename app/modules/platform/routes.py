"""FastAPI routes for the platform module — auth endpoints, fund info."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.modules.platform.auth_service import AuthService
from app.shared.auth import Permission, get_actor_context, require_permission
from app.shared.request_context import ActorType, RequestContext

router = APIRouter(tags=["platform"])


def _get_auth_service(request: Request) -> AuthService:
    service: AuthService | None = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="AuthService not initialized")
    return service


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


class FundInfo(BaseModel):
    fund_slug: str
    fund_name: str
    role: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me/funds", response_model=list[FundInfo])
async def list_my_funds(
    ctx: RequestContext = Depends(get_actor_context),
    auth: AuthService = Depends(_get_auth_service),
) -> list[FundInfo]:
    """Return all funds the authenticated user has access to.

    Requires authentication only — no specific permission needed.
    This endpoint bootstraps the fund selector before fund context exists.
    """
    funds = await auth.get_user_funds(ctx.actor_id)
    return [FundInfo(**f) for f in funds]


@router.post("/auth/agent-token", response_model=AgentTokenResponse)
async def create_agent_token(
    body: AgentTokenRequest,
    ctx: RequestContext = require_permission(Permission.FUNDS_MANAGE),
    auth: AuthService = Depends(_get_auth_service),
) -> AgentTokenResponse:
    """Issue a JWT for an LLM agent.

    Requires an authenticated user with ``funds:manage`` permission.
    The agent token is scoped to the caller's fund and carries the
    delegating user's ID for audit.
    """
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
