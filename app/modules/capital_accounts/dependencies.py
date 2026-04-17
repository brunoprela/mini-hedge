"""FastAPI dependency wrappers for the capital accounts module."""

from fastapi import HTTPException, Request

from app.modules.platform.repositories.investor import InvestorRepository
from app.modules.capital_accounts.services import CapitalAccountService, CapitalTransactionService


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


def get_investor_repo(request: Request) -> InvestorRepository:
    repo: InvestorRepository | None = getattr(request.app.state, "investor_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="InvestorRepository not initialized",
        )
    return repo


def get_capital_transaction_service(request: Request) -> CapitalTransactionService:
    service: CapitalTransactionService | None = getattr(
        request.app.state, "capital_transaction_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="CapitalTransactionService not initialized",
        )
    return service
