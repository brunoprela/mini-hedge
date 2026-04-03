"""FastAPI dependency wrappers for the security master module."""

from fastapi import HTTPException, Request

from app.modules.security_master.service import SecurityMasterService


def get_security_master_service(request: Request) -> SecurityMasterService:
    service: SecurityMasterService | None = getattr(
        request.app.state, "security_master_service", None
    )
    if service is None:
        raise HTTPException(status_code=503, detail="SecurityMasterService not initialized")
    return service
