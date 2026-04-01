"""FastAPI routes for market data."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.service import MarketDataService

router = APIRouter(prefix="/prices", tags=["market-data"])

_service: MarketDataService | None = None


def init_routes(service: MarketDataService) -> None:
    global _service
    _service = service


def _get_service() -> MarketDataService:
    assert _service is not None, "MarketDataService not initialized"
    return _service


@router.get("/latest/{instrument_id}", response_model=PriceSnapshot)
async def get_latest_price(instrument_id: str) -> PriceSnapshot:
    snapshot = await _get_service().get_latest_price(instrument_id.upper())
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No price data for {instrument_id}")
    return snapshot


@router.get("/history/{instrument_id}", response_model=list[PriceSnapshot])
async def get_price_history(
    instrument_id: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
) -> list[PriceSnapshot]:
    return await _get_service().get_price_history(instrument_id.upper(), start, end)
