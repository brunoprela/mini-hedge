"""FastAPI dependency wrappers for the platform module."""

from fastapi import HTTPException, Request

from app.modules.platform.auth_service import AuthService


def get_auth_service(request: Request) -> AuthService:
    service: AuthService | None = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="AuthService not initialized")
    return service
