"""FastAPI dependency wrappers for the cash management module."""

from fastapi import HTTPException, Request

from app.modules.cash_management.service import CashManagementService


def get_cash_service(request: Request) -> CashManagementService:
    service: CashManagementService | None = getattr(request.app.state, "cash_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="CashManagementService not initialized",
        )
    return service
