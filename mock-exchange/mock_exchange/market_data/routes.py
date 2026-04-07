"""Market data REST endpoints — modeled after Bloomberg BLPAPI HTTP gateway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from mock_exchange.shared.models import (
    OrderBookSnapshot,
    PriceQuote,
    TradeTick,
    VWAPData,
)

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


@router.get("/prices/{ticker}/book", response_model=OrderBookSnapshot)
async def get_order_book(
    request: Request, ticker: str, depth: int = Query(default=5, le=20),
) -> OrderBookSnapshot:
    """Get order book snapshot with bid/ask depth."""
    service = _get_service(request)
    snapshot = service.get_order_book_snapshot(ticker.upper(), depth=depth)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No order book for {ticker}")
    return snapshot


@router.get("/prices/{ticker}/vwap", response_model=VWAPData)
async def get_vwap(
    request: Request,
    ticker: str,
    minutes: int = Query(default=60, description="Lookback window in minutes"),
) -> VWAPData:
    """Get VWAP for an instrument over a time window."""
    service = _get_service(request)
    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes)
    vwap = service.get_vwap(ticker.upper(), start, end)
    if vwap is None:
        raise HTTPException(status_code=404, detail=f"No VWAP data for {ticker}")
    return vwap


@router.get("/prices/{ticker}/trades", response_model=list[TradeTick])
async def get_trades(
    request: Request,
    ticker: str,
    limit: int = Query(default=100, le=1000),
) -> list[TradeTick]:
    """Get recent trade ticks for an instrument."""
    service = _get_service(request)
    tape = service.trade_tape
    if tape is None:
        raise HTTPException(status_code=404, detail="Trade tape not available")
    return tape.recent_ticks(ticker.upper(), limit=limit)


@router.get("/prices/{ticker}/tca-benchmarks")
async def get_tca_benchmarks(
    request: Request,
    ticker: str,
    minutes: int = Query(default=60, description="VWAP lookback window in minutes"),
) -> dict:
    """Get TCA benchmark data: current price, VWAP, spread, volume."""
    service = _get_service(request)
    ticker = ticker.upper()

    quote = service.get_latest_price(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Instrument {ticker} not found")

    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes)
    vwap = service.get_vwap(ticker, start, end)

    return {
        "instrument_id": ticker,
        "mid": str(quote.mid),
        "bid": str(quote.bid),
        "ask": str(quote.ask),
        "spread_bps": float((quote.ask - quote.bid) / quote.mid * 10000) if quote.mid > 0 else 0,
        "vwap": str(vwap.vwap) if vwap else None,
        "vwap_volume": vwap.cumulative_volume if vwap else 0,
        "daily_volume": service.trade_tape.daily_volume(ticker) if service.trade_tape else 0,
        "timestamp": end.isoformat(),
    }
