"""FastAPI dependency wrappers for investor operations."""

from fastapi import HTTPException, Request

from app.modules.investor_operations.service import InvestorOperationsService


def get_investor_ops_service(request: Request) -> InvestorOperationsService:
    service: InvestorOperationsService | None = getattr(
        request.app.state, "investor_ops_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Investor operations module not initialized",
        )
    return service
