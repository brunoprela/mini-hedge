"""FastAPI dependency injection for regulatory module."""


from fastapi import HTTPException, Request

from app.modules.regulatory.services import RegulatoryService
from app.shared.auth import Permission, require_permission  # noqa: F401


def get_regulatory_service(request: Request) -> RegulatoryService:
    service: RegulatoryService | None = getattr(request.app.state, "regulatory_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Regulatory service unavailable")
    return service
