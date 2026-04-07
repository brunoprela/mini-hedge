"""FastAPI dependency wrappers for the capital accounts module."""

from fastapi import HTTPException, Request

from app.modules.capital_accounts.service import CapitalAccountService


def get_capital_account_service(request: Request) -> CapitalAccountService:
    service: CapitalAccountService | None = getattr(
        request.app.state, "capital_account_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="CapitalAccountService not initialized",
        )
    return service
