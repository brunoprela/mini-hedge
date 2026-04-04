"""Market data REST endpoints — modeled after Bloomberg BLPAPI HTTP gateway."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from mock_exchange.shared.models import PriceQuote

router = APIRouter(tags=["Market Data"])


def _get_service(request: Request):  # noqa: ANN202
    return request.app.state.market_data_service


@router.get("/prices", response_model=list[PriceQuote])
async def get_all_prices(request: Request) -> list[PriceQuote]:
    """Get latest prices for all instruments."""
    service = _get_service(request)
    return service.get_all_prices()


@router.get("/prices/{ticker}", response_model=PriceQuote)
async def get_price(request: Request, ticker: str) -> PriceQuote:
    """Get latest price for a single instrument."""
    service = _get_service(request)
    quote = service.get_latest_price(ticker.upper())
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Instrument {ticker} not found")
    return quote
