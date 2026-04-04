"""FastAPI dependency wrappers for the attribution module."""

from fastapi import HTTPException, Request

from app.modules.attribution.service import AttributionService


def get_attribution_service(request: Request) -> AttributionService:
    service: AttributionService | None = getattr(request.app.state, "attribution_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="AttributionService not initialized",
        )
    return service
