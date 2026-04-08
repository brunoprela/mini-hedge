"""FastAPI dependency injection for regulatory module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.shared.auth import Permission, require_permission  # noqa: F401

if TYPE_CHECKING:
    from fastapi import Request

    from app.modules.regulatory.service import RegulatoryService


def get_regulatory_service(request: Request) -> RegulatoryService:
    return request.app.state.regulatory_service
