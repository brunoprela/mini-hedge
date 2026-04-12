"""FastAPI dependency injection for regulatory module."""


from fastapi import Request

from app.modules.regulatory.services import RegulatoryService
from app.shared.auth import Permission, require_permission  # noqa: F401


def get_regulatory_service(request: Request) -> RegulatoryService:
    return request.app.state.regulatory_service
