"""FastAPI dependency wrappers for the risk engine module."""

from fastapi import HTTPException, Request

from app.modules.risk_engine.service import RiskService


def get_risk_service(request: Request) -> RiskService:
    service: RiskService | None = getattr(request.app.state, "risk_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="RiskService not initialized",
        )
    return service
