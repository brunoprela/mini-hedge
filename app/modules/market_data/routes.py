"""FastAPI routes for market data."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.market_data.dependencies import get_market_data_service
from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.service import MarketDataService
from app.shared.auth import Permission, require_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/prices", tags=["market-data"])


@router.get("/latest/{instrument_id}", response_model=PriceSnapshot)
async def get_latest_price(
    instrument_id: str,
    ctx: RequestContext = require_permission(Permission.PRICES_READ),
    service: MarketDataService = Depends(get_market_data_service),
) -> PriceSnapshot:
    snapshot = await service.get_latest_price(instrument_id.upper())
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No price data for {instrument_id}")
    return snapshot


@router.get("/history/{instrument_id}", response_model=list[PriceSnapshot])
async def get_price_history(
    instrument_id: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    ctx: RequestContext = require_permission(Permission.PRICES_READ),
    service: MarketDataService = Depends(get_market_data_service),
) -> list[PriceSnapshot]:
    return await service.get_price_history(instrument_id.upper(), start, end)
