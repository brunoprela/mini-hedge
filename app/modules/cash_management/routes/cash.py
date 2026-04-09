"""FastAPI routes for cash management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query

from app.modules.cash_management.core.holiday_calendar import HolidayCalendar
from app.modules.cash_management.core.messaging import (
    SettlementMessage,
    SettlementMessenger,
)
from app.modules.cash_management.core.netting import NettingEngine, NettingResult
from app.modules.cash_management.dependencies import get_cash_service
from app.modules.cash_management.interfaces import (
    CashBalance,
    CashProjection,
    SettlementLadder,
    SettlementRecord,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.fga import require_access
from app.shared.fga.resources import Portfolio

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.cash_management.services import CashManagementService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/cash", tags=["cash"])

# Singletons — lightweight, no external state
_holiday_calendar = HolidayCalendar()
_netting_engine = NettingEngine()
_messenger = SettlementMessenger()


# ------------------------------------------------------------------
# Existing endpoints
# ------------------------------------------------------------------


@router.get(
    "/{portfolio_id}/balances",
    response_model=list[CashBalance],
)
async def get_cash_balances(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[CashBalance]:
    return await cash_management_service.get_balances(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/settlements",
    response_model=list[SettlementRecord],
)
async def get_pending_settlements(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[SettlementRecord]:
    return await cash_management_service.get_pending_settlements(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/ladder",
    response_model=SettlementLadder,
)
async def get_settlement_ladder(
    portfolio_id: UUID,
    horizon_days: int = Query(default=10, ge=1, le=90),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> SettlementLadder:
    return await cash_management_service.get_settlement_ladder(
        portfolio_id, horizon_days, session=session
    )


@router.get(
    "/{portfolio_id}/projection",
    response_model=CashProjection,
)
async def get_cash_projection(
    portfolio_id: UUID,
    horizon_days: int = Query(default=30, ge=1, le=365),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> CashProjection:
    return await cash_management_service.get_projection(portfolio_id, horizon_days, session=session)


# ------------------------------------------------------------------
# Holiday calendar
# ------------------------------------------------------------------


@router.get(
    "/holidays/{country}/{year}",
    response_model=list[str],
)
async def get_holidays(
    country: str = Path(..., min_length=2, max_length=2),
    year: int = Path(..., ge=2024, le=2030),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
) -> list[str]:
    """List market holidays for a country and year."""
    holidays = _holiday_calendar.get_holidays(country.upper(), year)
    return [d.isoformat() for d in holidays]


# ------------------------------------------------------------------
# Netting
# ------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/netting",
    response_model=list[NettingResult],
)
async def compute_netting(
    portfolio_id: UUID,
    counterparty_map: dict[str, str] = Body(
        ..., description="Mapping of instrument_id to counterparty identifier"
    ),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[NettingResult]:
    """Compute netting for pending settlements in a portfolio."""
    settlements = await cash_management_service.get_pending_settlements(
        portfolio_id, session=session
    )
    # Convert SettlementRecord DTOs back to the model-like objects the
    # netting engine expects.  The engine only reads .id, .instrument_id,
    # .currency, .settlement_amount — all present on SettlementRecord too.
    return _netting_engine.compute_netting(settlements, counterparty_map)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# Settlement messaging
# ------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/settlements/{settlement_id}/message",
    response_model=SettlementMessage,
)
async def generate_settlement_message(
    portfolio_id: UUID,
    settlement_id: UUID,
    counterparty_bic: str = Body(..., embed=True),
    counterparty_name: str = Body(..., embed=True),
    request_context: RequestContext = require_permission(Permission.CASH_WRITE),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> SettlementMessage:
    """Generate a SWIFT-like settlement instruction for a settlement."""
    pending = await cash_management_service.get_pending_settlements(portfolio_id, session=session)
    settlement = next((s for s in pending if str(s.id) == str(settlement_id)), None)
    if settlement is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Settlement not found")
    return _messenger.generate_payment_instruction(
        settlement,  # type: ignore[arg-type]
        counterparty_bic=counterparty_bic,
        counterparty_name=counterparty_name,
    )


@router.get(
    "/{portfolio_id}/settlement-messages",
    response_model=list[dict[str, Any]],
)
async def list_settlement_messages(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Generate SWIFT-like messages for all pending settlements.

    This is a convenience endpoint that generates MT103/MT210 messages for
    every pending settlement.  Since no counterparty BIC registry exists
    yet, a placeholder BIC is used.
    """
    pending = await cash_management_service.get_pending_settlements(portfolio_id, session=session)
    messages: list[dict[str, Any]] = []
    for settlement in pending:
        msg = _messenger.generate_payment_instruction(
            settlement,  # type: ignore[arg-type]
            counterparty_bic="CPTYUS33XXX",
            counterparty_name="Counterparty",
        )
        messages.append(msg.model_dump(mode="json"))
    return messages
