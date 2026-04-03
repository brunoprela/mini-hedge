"""FastAPI dependency wrappers for the exposure module."""

from fastapi import HTTPException, Request

from app.modules.exposure.service import ExposureService


def get_exposure_service(request: Request) -> ExposureService:
    service: ExposureService | None = getattr(
        request.app.state, "exposure_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="ExposureService not initialized",
        )
    return service
