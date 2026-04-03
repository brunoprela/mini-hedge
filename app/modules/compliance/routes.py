"""FastAPI routes for compliance module."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.modules.compliance.dependencies import (
    get_compliance_service,
)
from app.modules.compliance.interface import (
    ComplianceDecision,
    RuleDefinition,
    RuleType,
    Severity,
    TradeCheckRequest,
    Violation,
)
from app.modules.compliance.service import ComplianceService
from app.shared.auth import Permission, require_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ---------------------------------------------------------------------------
# Request / response bodies
# ---------------------------------------------------------------------------


class CreateRuleBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    rule_type: RuleType
    severity: Severity
    parameters: dict[str, object] = {}


class UpdateRuleBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str | None = None
    rule_type: RuleType | None = None
    severity: Severity | None = None
    parameters: dict[str, object] | None = None
    is_active: bool | None = None


class ResolveBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    resolved_by: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[RuleDefinition])
async def list_rules(
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    service: ComplianceService = Depends(get_compliance_service),
) -> list[RuleDefinition]:
    return await service.get_rules(ctx.fund_slug)


@router.post("/rules", response_model=RuleDefinition, status_code=201)
async def create_rule(
    body: CreateRuleBody,
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    service: ComplianceService = Depends(get_compliance_service),
) -> RuleDefinition:
    return await service.create_rule(
        fund_slug=ctx.fund_slug,
        name=body.name,
        rule_type=body.rule_type,
        severity=body.severity,
        parameters=body.parameters,
    )


@router.patch("/rules/{rule_id}", response_model=RuleDefinition)
async def update_rule(
    rule_id: UUID,
    body: UpdateRuleBody,
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    service: ComplianceService = Depends(get_compliance_service),
) -> RuleDefinition:
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )
    try:
        return await service.update_rule(rule_id, **fields)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/check", response_model=ComplianceDecision)
async def check_trade(
    body: TradeCheckRequest,
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    service: ComplianceService = Depends(get_compliance_service),
) -> ComplianceDecision:
    return await service.check_trade(body, ctx.fund_slug)


@router.get("/violations", response_model=list[Violation])
async def list_violations(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    service: ComplianceService = Depends(get_compliance_service),
) -> list[Violation]:
    return await service.get_violations(portfolio_id)


@router.post(
    "/violations/{violation_id}/resolve",
    response_model=Violation,
)
async def resolve_violation(
    violation_id: UUID,
    body: ResolveBody,
    ctx: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    service: ComplianceService = Depends(get_compliance_service),
) -> Violation:
    try:
        return await service.resolve_violation(violation_id, body.resolved_by)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
