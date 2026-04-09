"""FastAPI dependency wrappers for the FX hedging module."""

from fastapi import HTTPException, Request

from app.modules.fx_hedging.services import FXHedgingService


def get_fx_hedging_service(request: Request) -> FXHedgingService:
    service: FXHedgingService | None = getattr(
        request.app.state,
        "fx_hedging_service",
        None,
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="FXHedgingService not initialized",
        )
    return service
