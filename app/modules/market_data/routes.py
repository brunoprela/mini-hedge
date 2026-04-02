"""FastAPI routes for market data."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.service import MarketDataService
from app.shared.auth import Permission, require_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/prices", tags=["market-data"])


def _get_service(request: Request) -> MarketDataService:
    service: MarketDataService | None = getattr(request.app.state, "market_data_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="MarketDataService not initialized")
    return service


@router.get("/latest/{instrument_id}", response_model=PriceSnapshot)
async def get_latest_price(
    request: Request,
    instrument_id: str,
    ctx: RequestContext = require_permission(Permission.PRICES_READ),
) -> PriceSnapshot:
    snapshot = await _get_service(request).get_latest_price(instrument_id.upper())
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No price data for {instrument_id}")
    return snapshot


@router.get("/history/{instrument_id}", response_model=list[PriceSnapshot])
async def get_price_history(
    request: Request,
    instrument_id: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    ctx: RequestContext = require_permission(Permission.PRICES_READ),
) -> list[PriceSnapshot]:
    return await _get_service(request).get_price_history(instrument_id.upper(), start, end)
