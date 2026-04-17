"""FastAPI routes for the corporate actions module."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.corporate_actions.dependencies import get_corporate_actions_service
from app.modules.corporate_actions.interfaces import ProcessedAction
from app.modules.corporate_actions.services import CorporateActionsService
from app.modules.platform.dependencies import get_portfolio_repo
from app.modules.platform.repositories import PortfolioRepository
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

router = APIRouter(prefix="/corporate-actions", tags=["corporate-actions"])


class ProcessCorporateActionsRequest(BaseModel):
    start_date: date
    end_date: date
    portfolio_id: str | None = None


@router.get("", response_model=list[ProcessedAction])
async def list_corporate_actions(
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    service: CorporateActionsService = Depends(get_corporate_actions_service),
    session: AsyncSession = Depends(get_db),
) -> list[ProcessedAction]:
    return await service.list_processed(session=session)


@router.post("/process", response_model=list[ProcessedAction], status_code=200)
async def process_corporate_actions(
    body: ProcessCorporateActionsRequest,
    request_context: RequestContext = require_permission(Permission.POSITIONS_WRITE),
    service: CorporateActionsService = Depends(get_corporate_actions_service),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> list[ProcessedAction]:
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")

    if body.portfolio_id is not None:
        portfolio_ids = [body.portfolio_id]
    else:
        fund_id = request_context.fund_id
        if fund_id is None:
            raise HTTPException(status_code=400, detail="Fund id required in context")
        portfolios = await portfolio_repo.get_by_fund(fund_id, session=session)
        portfolio_ids = [p.id for p in portfolios]

    results: list[ProcessedAction] = []
    for portfolio_id in portfolio_ids:
        processed = await service.fetch_and_process(
            fund_slug=request_context.fund_slug,
            portfolio_id=portfolio_id,
            start_date=body.start_date,
            end_date=body.end_date,
            session=session,
        )
        results.extend(processed)
    return results
