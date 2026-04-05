"""FastAPI routes for risk engine."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.shared.database import get_db
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
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> RiskSnapshot | None:
    return await risk_service.get_latest_snapshot(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/snapshot/history",
    response_model=list[RiskSnapshot],
)
async def get_risk_history(
    portfolio_id: UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> list[RiskSnapshot]:
    return await risk_service.get_snapshot_history(portfolio_id, start, end, session=session)


@router.post("/{portfolio_id}/snapshot", response_model=RiskSnapshot)
async def take_risk_snapshot(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> RiskSnapshot:
    return await risk_service.take_snapshot(portfolio_id, session=session)


@router.post("/{portfolio_id}/var", response_model=VaRResult)
async def calculate_var(
    portfolio_id: UUID,
    body: VaRRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> VaRResult:
    return await risk_service.calculate_var(
        portfolio_id,
        method=body.method,
        confidence=body.confidence,
        horizon_days=body.horizon_days,
        session=session,
    )


@router.get(
    "/{portfolio_id}/stress",
    response_model=list[StressTestResult],
)
async def run_predefined_stress_tests(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> list[StressTestResult]:
    results = []
    for scenario in PREDEFINED_SCENARIOS:
        result = await risk_service.run_stress_test(portfolio_id, scenario, session=session)
        results.append(result)
    return results


@router.post(
    "/{portfolio_id}/stress",
    response_model=StressTestResult,
)
async def run_custom_stress_test(
    portfolio_id: UUID,
    body: CustomStressRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> StressTestResult:
    scenario = StressScenario(
        name=body.name,
        scenario_type=StressScenarioType.CUSTOM,
        shocks=body.shocks,
        description=body.description,
    )
    return await risk_service.run_stress_test(portfolio_id, scenario, session=session)


@router.get(
    "/{portfolio_id}/factors",
    response_model=FactorDecomposition,
)
async def get_factor_decomposition(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    risk_service: RiskService = Depends(get_risk_service),
    session: AsyncSession = Depends(get_db),
) -> FactorDecomposition:
    return await risk_service.calculate_factor_model(portfolio_id, session=session)


@router.get("/scenarios", response_model=list[dict])
async def list_predefined_scenarios(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
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
