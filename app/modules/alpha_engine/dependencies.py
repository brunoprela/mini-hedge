"""FastAPI dependency wrappers for the alpha engine module."""

from fastapi import HTTPException, Request

from app.modules.alpha_engine.service import AlphaService


def get_alpha_service(request: Request) -> AlphaService:
    service: AlphaService | None = getattr(request.app.state, "alpha_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="AlphaService not initialized",
        )
    return service
