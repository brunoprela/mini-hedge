"""FastAPI dependency wrappers for the corporate actions module."""

from fastapi import HTTPException, Request

from app.modules.corporate_actions.services import CorporateActionsService


def get_corporate_actions_service(request: Request) -> CorporateActionsService:
    service: CorporateActionsService | None = getattr(
        request.app.state, "corporate_actions_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="CorporateActionsService not initialized",
        )
    return service
