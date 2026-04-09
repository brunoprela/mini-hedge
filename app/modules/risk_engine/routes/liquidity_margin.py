"""FastAPI routes for liquidity risk and margin management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.risk_engine.dependencies import get_liquidity_margin_service
from app.modules.risk_engine.interfaces.liquidity import LiquidityProfile
from app.modules.risk_engine.interfaces.margin import MarginSummary
from app.modules.risk_engine.services import LiquidityMarginService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/liquidity", response_model=LiquidityProfile)
async def get_liquidity_profile(
    portfolio_id: UUID = Query(...),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    liquidity_margin_service: LiquidityMarginService = Depends(get_liquidity_margin_service),
    session: AsyncSession = Depends(get_db),
) -> LiquidityProfile:
    return await liquidity_margin_service.calculate_liquidity(portfolio_id, session=session)


@router.get("/margin", response_model=MarginSummary)
async def get_margin_summary(
    portfolio_id: UUID = Query(...),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    liquidity_margin_service: LiquidityMarginService = Depends(get_liquidity_margin_service),
    session: AsyncSession = Depends(get_db),
) -> MarginSummary:
    return await liquidity_margin_service.calculate_margin(portfolio_id, session=session)
