"""FastAPI routes for exposure calculation."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.modules.exposure.dependencies import get_exposure_service
from app.modules.exposure.interface import (
    ExposureSnapshot,
    PortfolioExposure,
)
from app.modules.exposure.service import ExposureService
from app.shared.auth import Permission, require_permission
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/exposure", tags=["exposure"])


@router.get("/{portfolio_id}", response_model=PortfolioExposure)
async def get_portfolio_exposure(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.EXPOSURE_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: ExposureService = Depends(get_exposure_service),
) -> PortfolioExposure:
    return await service.get_current(portfolio_id)


@router.get(
    "/{portfolio_id}/history",
    response_model=list[ExposureSnapshot],
)
async def get_exposure_history(
    portfolio_id: UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    ctx: RequestContext = require_permission(Permission.EXPOSURE_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: ExposureService = Depends(get_exposure_service),
) -> list[ExposureSnapshot]:
    return await service.get_history(portfolio_id, start, end, fund_slug=ctx.fund_slug)
