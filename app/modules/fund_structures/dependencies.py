"""FastAPI dependency wrappers for the fund structures module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from app.modules.fund_structures.service import FundStructuresService


def get_fund_structures_service(request: Request) -> FundStructuresService:
    service: FundStructuresService | None = getattr(
        request.app.state,
        "fund_structures_service",
        None,
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="FundStructuresService not initialized",
        )
    return service
