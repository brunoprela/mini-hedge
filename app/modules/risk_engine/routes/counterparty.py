"""FastAPI routes for counterparty and credit risk."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.risk_engine.dependencies import get_counterparty_risk_service
from app.modules.risk_engine.interfaces.counterparty import CounterpartyExposure
from app.modules.risk_engine.services import CounterpartyRiskService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_read_db

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/counterparties", response_model=list[dict[str, object]])
async def list_counterparties(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    counterparty_risk_service: CounterpartyRiskService = Depends(get_counterparty_risk_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[dict[str, object]]:
    items = await counterparty_risk_service.list_counterparties(session=session)
    return [
        {
            "id": str(i.id),
            "name": i.name,
            "type": i.counterparty_type,
            "credit_rating": i.credit_rating,
            "credit_limit": str(i.credit_limit),
            "netting_eligible": i.netting_eligible,
        }
        for i in items
    ]


@router.get(
    "/counterparty-exposures",
    response_model=list[CounterpartyExposure],
)
async def get_counterparty_exposures(
    portfolio_id: UUID = Query(...),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    counterparty_risk_service: CounterpartyRiskService = Depends(get_counterparty_risk_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[CounterpartyExposure]:
    return await counterparty_risk_service.get_counterparty_exposures(portfolio_id, session=session)
