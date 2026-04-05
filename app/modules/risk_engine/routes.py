"""FastAPI routes for risk engine."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.modules.risk_engine.dependencies import get_risk_service
from app.modules.risk_engine.interface import (
    PREDEFINED_SCENARIOS,
    FactorDecomposition,
    RiskSnapshot,
    StressScenario,
    StressScenarioType,
    StressTestResult,
    VaRMethod,
    VaRResult,
)
from app.modules.risk_engine.service import RiskService
from app.shared.auth import Permission, require_permission
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/risk", tags=["risk"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class VaRRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: VaRMethod = VaRMethod.HISTORICAL
    confidence: float = 0.95
    horizon_days: int = 1


class CustomStressRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    shocks: dict[str, float]
    description: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{portfolio_id}/snapshot", response_model=RiskSnapshot | None)
async def get_risk_snapshot(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> RiskSnapshot | None:
    return await service.get_latest_snapshot(portfolio_id)


@router.get(
    "/{portfolio_id}/snapshot/history",
    response_model=list[RiskSnapshot],
)
async def get_risk_history(
    portfolio_id: UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> list[RiskSnapshot]:
    return await service.get_snapshot_history(portfolio_id, start, end)


@router.post("/{portfolio_id}/snapshot", response_model=RiskSnapshot)
async def take_risk_snapshot(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> RiskSnapshot:
    return await service.take_snapshot(portfolio_id)


@router.post("/{portfolio_id}/var", response_model=VaRResult)
async def calculate_var(
    portfolio_id: UUID,
    body: VaRRequest,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> VaRResult:
    return await service.calculate_var(
        portfolio_id,
        method=body.method,
        confidence=body.confidence,
        horizon_days=body.horizon_days,
    )


@router.get(
    "/{portfolio_id}/stress",
    response_model=list[StressTestResult],
)
async def run_predefined_stress_tests(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> list[StressTestResult]:
    results = []
    for scenario in PREDEFINED_SCENARIOS:
        result = await service.run_stress_test(portfolio_id, scenario)
        results.append(result)
    return results


@router.post(
    "/{portfolio_id}/stress",
    response_model=StressTestResult,
)
async def run_custom_stress_test(
    portfolio_id: UUID,
    body: CustomStressRequest,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> StressTestResult:
    scenario = StressScenario(
        name=body.name,
        scenario_type=StressScenarioType.CUSTOM,
        shocks=body.shocks,
        description=body.description,
    )
    return await service.run_stress_test(portfolio_id, scenario)


@router.get(
    "/{portfolio_id}/factors",
    response_model=FactorDecomposition,
)
async def get_factor_decomposition(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: RiskService = Depends(get_risk_service),
) -> FactorDecomposition:
    return await service.calculate_factor_model(portfolio_id)


@router.get("/scenarios", response_model=list[dict])
async def list_predefined_scenarios(
    ctx: RequestContext = require_permission(Permission.RISK_READ),
) -> list[dict]:
    """List available predefined stress scenarios."""
    return [
        {
            "name": s.name,
            "description": s.description,
            "shocks": s.shocks,
        }
        for s in PREDEFINED_SCENARIOS
    ]
