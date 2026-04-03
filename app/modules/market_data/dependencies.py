"""FastAPI dependency wrappers for the market data module."""

from fastapi import HTTPException, Request

from app.modules.market_data.service import MarketDataService


def get_market_data_service(request: Request) -> MarketDataService:
    service: MarketDataService | None = getattr(request.app.state, "market_data_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="MarketDataService not initialized")
    return service
