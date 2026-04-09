"""FastAPI dependency wrappers for the fee accounting module."""

from fastapi import HTTPException, Request

from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
from app.modules.fee_accounting.services import FeeAccountingService


def get_fee_accounting_service(request: Request) -> FeeAccountingService:
    service: FeeAccountingService | None = getattr(
        request.app.state, "fee_accounting_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="FeeAccountingService not initialized",
        )
    return service


def get_fee_schedule_repo(request: Request) -> FeeScheduleRepository:
    repo: FeeScheduleRepository | None = getattr(request.app.state, "fee_schedule_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="FeeScheduleRepository not initialized",
        )
    return repo
