"""Reference data REST endpoints — modeled after DTCC / Bloomberg FIGI patterns."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from mock_exchange.shared.models import InstrumentInfo

from .instruments import get_all_instruments, get_instrument

router = APIRouter(tags=["Reference Data"])


@router.get("/instruments", response_model=list[InstrumentInfo])
async def list_instruments(
    asset_class: str | None = None,
    country: str | None = None,
    sector: str | None = None,
) -> list[InstrumentInfo]:
    """List all instruments, optionally filtered."""
    return get_all_instruments(asset_class=asset_class, country=country, sector=sector)


@router.get("/instruments/{ticker}", response_model=InstrumentInfo)
async def get_instrument_detail(ticker: str) -> InstrumentInfo:
    """Get instrument details by ticker."""
    info = get_instrument(ticker.upper())
    if info is None:
        raise HTTPException(status_code=404, detail=f"Instrument {ticker} not found")
    return info
