"""FastAPI dependency wrappers for the compliance module."""

from fastapi import HTTPException, Request

from app.modules.compliance.service import ComplianceService


def get_compliance_service(
    request: Request,
) -> ComplianceService:
    service: ComplianceService | None = getattr(request.app.state, "compliance_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="ComplianceService not initialized",
        )
    return service
