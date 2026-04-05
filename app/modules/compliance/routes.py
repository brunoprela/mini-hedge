"""FastAPI routes for compliance module."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.compliance.dependencies import (
    get_compliance_service,
)
from app.modules.compliance.interface import (
    ComplianceDecision,
    RemediationSuggestion,
    RuleDefinition,
    RuleType,
    Severity,
    TradeCheckRequest,
    UpdateRuleRequest,
    Violation,
)
from app.modules.compliance.service import ComplianceService
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
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


class ResolveBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    resolved_by: str


class WaiveBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    waived_by: str
    reason: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[RuleDefinition])
async def list_rules(
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> list[RuleDefinition]:
    return await compliance_service.get_rules(session=session)


@router.post("/rules", response_model=RuleDefinition, status_code=201)
async def create_rule(
    body: CreateRuleBody,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> RuleDefinition:
    return await compliance_service.create_rule(
        name=body.name,
        rule_type=body.rule_type,
        severity=body.severity,
        parameters=body.parameters,
        actor_id=request_context.actor_id,
        session=session,
    )


@router.patch("/rules/{rule_id}", response_model=RuleDefinition)
async def update_rule(
    rule_id: UUID,
    body: UpdateRuleRequest,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> RuleDefinition:
    if not body.model_dump(exclude_none=True):
        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )
    try:
        return await compliance_service.update_rule(
            rule_id, body, actor_id=request_context.actor_id, session=session
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/check", response_model=ComplianceDecision)
async def check_trade(
    body: TradeCheckRequest,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> ComplianceDecision:
    return await compliance_service.check_trade(body, session=session)


@router.get("/violations", response_model=list[Violation])
async def list_violations(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> list[Violation]:
    return await compliance_service.get_violations(portfolio_id, session=session)


@router.post(
    "/violations/{violation_id}/resolve",
    response_model=Violation,
)
async def resolve_violation(
    violation_id: UUID,
    body: ResolveBody,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> Violation:
    try:
        return await compliance_service.resolve_violation(
            violation_id, body.resolved_by, session=session
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/violations/{violation_id}/waive",
    response_model=Violation,
)
async def waive_violation(
    violation_id: UUID,
    body: WaiveBody,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> Violation:
    try:
        return await compliance_service.waive_violation(
            violation_id, body.waived_by, body.reason, session=session
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/violations/remediation",
    response_model=list[RemediationSuggestion],
)
async def suggest_remediation(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    compliance_service: ComplianceService = Depends(get_compliance_service),
    session: AsyncSession = Depends(get_db),
) -> list[RemediationSuggestion]:
    """Suggest trades to cure active compliance violations."""
    return await compliance_service.suggest_remediation(portfolio_id, session=session)
