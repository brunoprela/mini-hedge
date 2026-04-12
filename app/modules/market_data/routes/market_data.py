"""FastAPI routes for market data."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.dependencies import get_market_data_service
from app.modules.market_data.interfaces import FXRateSnapshot, OHLCVBar, PriceSnapshot
from app.modules.market_data.services import MarketDataService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_read_db

router = APIRouter(prefix="/prices", tags=["market_data"])
fx_router = APIRouter(prefix="/fx", tags=["market_data"])
vol_router = APIRouter(prefix="/volatility", tags=["market_data"])


@router.get("/latest/{instrument_id}", response_model=PriceSnapshot)
async def get_latest_price(
    instrument_id: str,
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> PriceSnapshot:
    snapshot = await market_data_service.get_latest_price(instrument_id.upper(), session=session)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No price data for {instrument_id}")
    return snapshot


@router.get("/history/{instrument_id}", response_model=list[PriceSnapshot])
async def get_price_history(
    instrument_id: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[PriceSnapshot]:
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be before end")
    return await market_data_service.get_price_history(
        instrument_id.upper(), start, end, session=session
    )


@router.get("/bars/{instrument_id}", response_model=list[OHLCVBar])
async def get_ohlcv_bars(
    instrument_id: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("1 day", description="Bucket width, e.g. '1 hour', '1 day', '5 minutes'"),
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[OHLCVBar]:
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be before end")
    return await market_data_service.get_ohlcv_bars(
        instrument_id.upper(), start, end, interval, session=session
    )


# ── FX rate endpoints ────────────────────────────────────────


@fx_router.get("/rates", response_model=list[FXRateSnapshot])
async def get_all_fx_rates(
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FXRateSnapshot]:
    return await market_data_service.get_all_fx_rates(session=session)


@fx_router.get("/rates/{base}/{quote}", response_model=FXRateSnapshot)
async def get_fx_rate(
    base: str,
    quote: str,
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    market_data_service: MarketDataService = Depends(get_market_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> FXRateSnapshot:
    snapshot = await market_data_service.get_fx_rate(base.upper(), quote.upper(), session=session)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No FX rate for {base}/{quote}")
    return snapshot


# ── Volatility surface endpoints ────────────────────────────


@vol_router.get("/surface/{instrument_id}")
async def get_volatility_surface(
    instrument_id: str,
    expiry: date | None = Query(None, description="Filter by expiry date"),
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    request: Request = None,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_read_db),
) -> list[dict]:
    from app.modules.market_data.repositories import VolatilitySurfaceRepository

    repo: VolatilitySurfaceRepository = request.app.state.vol_surface_repo
    if expiry:
        records = await repo.get_surface(instrument_id.upper(), expiry, session=session)
    else:
        records = await repo.get_latest_surface(instrument_id.upper(), session=session)
    return [
        {
            "instrument_id": r.instrument_id,
            "expiry": r.expiry.isoformat(),
            "strike": str(r.strike),
            "implied_vol": str(r.implied_vol),
            "delta": str(r.delta) if r.delta else None,
            "timestamp": r.timestamp.isoformat(),
            "source": r.source,
        }
        for r in records
    ]


@vol_router.get("/surface/{instrument_id}/expiries")
async def get_vol_surface_expiries(
    instrument_id: str,
    request_context: RequestContext = require_permission(Permission.PRICES_READ),
    request: Request = None,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_read_db),
) -> list[str]:
    from app.modules.market_data.repositories import VolatilitySurfaceRepository

    repo: VolatilitySurfaceRepository = request.app.state.vol_surface_repo
    expiries = await repo.get_expiries(instrument_id.upper(), session=session)
    return [e.isoformat() for e in expiries]
