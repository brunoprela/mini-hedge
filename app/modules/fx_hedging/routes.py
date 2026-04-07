"""FastAPI routes for FX hedging — forwards, MTM, recommendations."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.modules.exposure.dependencies import get_exposure_service
from app.modules.fx_hedging.dependencies import get_fx_hedging_service
from app.modules.fx_hedging.interface import (
    FXForwardClose,
    FXForwardContract,
    FXForwardCreate,
    FXForwardRoll,
    FXHedgingSummary,
    FXInterestRate,
    HedgeRecommendationResponse,
    RollRecommendation,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_read_db
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.exposure.service import ExposureService
    from app.modules.fx_hedging.service import FXHedgingService
    from app.shared.request_context import RequestContext

router = APIRouter(prefix="/fx-hedging", tags=["fx-hedging"])


# -- Forward CRUD ----------------------------------------------------------


@router.get("/forwards/{portfolio_id}", response_model=list[FXForwardContract])
async def list_forwards(
    portfolio_id: UUID,
    status: str | None = Query(None),
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FXForwardContract]:
    return await service.get_forwards(portfolio_id, status=status, session=session)


@router.get("/forwards/{portfolio_id}/{forward_id}", response_model=FXForwardContract)
async def get_forward(
    portfolio_id: UUID,
    forward_id: UUID,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXForwardContract:
    result = await service.get_forward(forward_id, session=session)
    if result is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Forward not found")
    return result


@router.post("/forwards", response_model=FXForwardContract, status_code=201)
async def open_forward(
    create: FXForwardCreate,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXForwardContract:
    return await service.open_forward(
        create,
        fund_slug=request_context.fund_slug,
        session=session,
    )


@router.post(
    "/forwards/{forward_id}/close",
    response_model=FXForwardContract,
)
async def close_forward(
    forward_id: UUID,
    close: FXForwardClose,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXForwardContract:
    return await service.close_forward(
        forward_id,
        close_rate=close.close_rate,
        close_spot=close.close_spot,
        fund_slug=request_context.fund_slug,
        session=session,
    )


@router.post(
    "/forwards/{forward_id}/roll",
    response_model=FXForwardContract,
    status_code=201,
)
async def roll_forward(
    forward_id: UUID,
    roll: FXForwardRoll,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXForwardContract:
    return await service.roll_forward(
        forward_id,
        new_maturity_date=roll.new_maturity_date,
        new_contract_rate=roll.new_contract_rate,
        current_spot=roll.current_spot,
        fund_slug=request_context.fund_slug,
        session=session,
    )


# -- Mark-to-market --------------------------------------------------------


@router.post(
    "/mtm/{portfolio_id}",
    response_model=list[FXForwardContract],
)
async def mark_to_market(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_WRITE),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FXForwardContract]:
    return await service.mark_to_market_all(
        portfolio_id,
        fund_slug=request_context.fund_slug,
        session=session,
    )


# -- Summary ---------------------------------------------------------------


@router.get("/summary/{portfolio_id}", response_model=FXHedgingSummary)
async def get_summary(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXHedgingSummary:
    return await service.get_summary(portfolio_id, session=session)


# -- Recommendations ------------------------------------------------------


@router.get(
    "/recommendations/{portfolio_id}/hedges",
    response_model=list[HedgeRecommendationResponse],
)
async def get_hedge_recommendations(
    portfolio_id: UUID,
    hedge_ratio: Decimal = Query(Decimal("1.0")),
    tenor_days: int = Query(30),
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    exposure_service: ExposureService = Depends(get_exposure_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[HedgeRecommendationResponse]:
    # Pull live currency exposures from the exposure module
    exposure = await exposure_service.get_current(portfolio_id, session=session)
    currency_exposures: dict[str, Decimal] = {}
    for breakdown in exposure.breakdowns.get("currency", []):
        if breakdown.net_value != 0:
            currency_exposures[breakdown.key] = breakdown.net_value

    return await service.get_hedge_recommendations(
        portfolio_id,
        currency_exposures=currency_exposures,
        hedge_ratio=hedge_ratio,
        tenor_days=tenor_days,
        fund_slug=request_context.fund_slug,
        session=session,
    )


@router.get(
    "/recommendations/{portfolio_id}/rolls",
    response_model=list[RollRecommendation],
)
async def get_roll_recommendations(
    portfolio_id: UUID,
    days_ahead: int = Query(5),
    new_tenor_days: int = Query(30),
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[RollRecommendation]:
    return await service.get_roll_recommendations(
        portfolio_id,
        days_ahead=days_ahead,
        new_tenor_days=new_tenor_days,
        session=session,
    )


# -- Interest rates --------------------------------------------------------


@router.get("/interest-rates", response_model=list[FXInterestRate])
async def list_interest_rates(
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_READ),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FXInterestRate]:
    records = await service.get_interest_rates(session=session)
    return [
        FXInterestRate(
            currency=r.currency,
            rate=r.rate,
            tenor_days=r.tenor_days,
            source=r.source,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.put("/interest-rates/{currency}", status_code=204)
async def set_interest_rate(
    currency: str,
    rate: Decimal = Query(...),
    tenor_days: int = Query(30),
    source: str = Query("manual"),
    request_context: RequestContext = require_permission(Permission.FX_HEDGING_WRITE),
    service: FXHedgingService = Depends(get_fx_hedging_service),
    session: AsyncSession = Depends(get_read_db),
) -> None:
    await service.set_interest_rate(
        currency,
        rate,
        tenor_days=tenor_days,
        source=source,
        session=session,
    )
