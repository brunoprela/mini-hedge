"""FastAPI routes for the corporate actions module."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.modules.corporate_actions.dependencies import get_corporate_actions_service
from app.modules.corporate_actions.interface import ProcessedAction
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.corporate_actions.service import CorporateActionsService
    from app.shared.request_context import RequestContext

router = APIRouter(prefix="/corporate-actions", tags=["corporate-actions"])


@router.get("", response_model=list[ProcessedAction])
async def list_corporate_actions(
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    service: CorporateActionsService = Depends(get_corporate_actions_service),
    session: AsyncSession = Depends(get_db),
) -> list[ProcessedAction]:
    return await service.list_processed(session=session)


@router.post("/process", response_model=list[ProcessedAction], status_code=200)
async def process_corporate_actions(
    portfolio_id: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    request_context: RequestContext = require_permission(Permission.POSITIONS_WRITE),
    service: CorporateActionsService = Depends(get_corporate_actions_service),
    session: AsyncSession = Depends(get_db),
) -> list[ProcessedAction]:
    if not request_context.fund_slug:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Fund context required")
    return await service.fetch_and_process(
        fund_slug=request_context.fund_slug,
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        session=session,
    )
