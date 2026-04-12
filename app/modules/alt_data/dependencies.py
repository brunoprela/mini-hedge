"""FastAPI dependency wrappers for the alt_data module."""


from fastapi import HTTPException, Request

from app.modules.alt_data.services import AltDataService


def get_alt_data_service(request: Request) -> AltDataService:
    service: AltDataService | None = getattr(request.app.state, "alt_data_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="AltDataService not initialized",
        )
    return service
