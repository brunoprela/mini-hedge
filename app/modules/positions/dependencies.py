"""FastAPI dependency wrappers for the positions module."""

from fastapi import HTTPException, Request

from app.modules.positions.service import PositionService


def get_position_service(request: Request) -> PositionService:
    service: PositionService | None = getattr(request.app.state, "position_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="PositionService not initialized")
    return service
