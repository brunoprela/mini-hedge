"""FastAPI dependency wrappers for the backtesting module."""


from fastapi import HTTPException, Request

from app.modules.backtesting.services import BacktestingService


def get_backtesting_service(request: Request) -> BacktestingService:
    service: BacktestingService | None = getattr(
        request.app.state,
        "backtesting_service",
        None,
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="BacktestingService not initialized",
        )
    return service
