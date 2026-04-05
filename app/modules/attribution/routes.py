"""FastAPI routes for performance attribution."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attribution.attribution_service import AttributionService
from app.modules.attribution.dependencies import get_attribution_service
from app.modules.attribution.interface import (
    BrinsonFachlerResult,
    CumulativeAttribution,
    RiskBasedResult,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/attribution", tags=["attribution"])


@router.get(
    "/{portfolio_id}/brinson-fachler",
    response_model=BrinsonFachlerResult,
)
async def get_brinson_fachler(
    portfolio_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    request_context: RequestContext = require_permission(Permission.ATTRIBUTION_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    attribution_service: AttributionService = Depends(get_attribution_service),
    session: AsyncSession = Depends(get_db),
) -> BrinsonFachlerResult:
    return await attribution_service.calculate_brinson_fachler(
        portfolio_id, start, end, session=session
    )


@router.get(
    "/{portfolio_id}/risk-based",
    response_model=RiskBasedResult,
)
async def get_risk_based(
    portfolio_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    request_context: RequestContext = require_permission(Permission.ATTRIBUTION_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    attribution_service: AttributionService = Depends(get_attribution_service),
    session: AsyncSession = Depends(get_db),
) -> RiskBasedResult:
    return await attribution_service.calculate_risk_based(portfolio_id, start, end, session=session)


@router.get(
    "/{portfolio_id}/cumulative",
    response_model=CumulativeAttribution,
)
async def get_cumulative_attribution(
    portfolio_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    request_context: RequestContext = require_permission(Permission.ATTRIBUTION_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    attribution_service: AttributionService = Depends(get_attribution_service),
    session: AsyncSession = Depends(get_db),
) -> CumulativeAttribution:
    return await attribution_service.calculate_cumulative(portfolio_id, start, end, session=session)
