"""NAV calculation — the single most important number a fund produces daily.

NAV = sum(position_market_values) + cash_balances - accrued_fees
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.eod.interface import NAVSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.cash_management.service import CashManagementService
    from app.modules.eod.repository import NAVSnapshotRepository
    from app.modules.positions.service import PositionService

logger = structlog.get_logger()

ZERO = Decimal(0)
_DEFAULT_SHARES = Decimal(1000)


class NAVCalculator:
    """Calculates NAV using finalized prices and reconciled positions."""

    def __init__(
        self,
        *,
        position_service: PositionService,
        cash_service: CashManagementService,
        nav_repo: NAVSnapshotRepository,
    ) -> None:
        self._positions = position_service
        self._cash = cash_service
        self._nav_repo = nav_repo

    async def calculate_nav(
        self,
        portfolio_id: UUID,
        business_date: date,
        *,
        currency: str = "USD",
        session: AsyncSession | None = None,
    ) -> NAVSnapshot:
        """Calculate and persist NAV for a portfolio on a business date."""
        positions = await self._positions.get_by_portfolio(portfolio_id, session=session)

        gross_market_value = sum(abs(p.market_value) for p in positions) if positions else ZERO
        net_market_value = sum(p.market_value for p in positions) if positions else ZERO

        cash_balances = await self._cash.get_balances(portfolio_id, session=session)
        cash_balance = sum(b.total_balance for b in cash_balances) if cash_balances else ZERO

        accrued_fees = ZERO
        nav = net_market_value + cash_balance - accrued_fees
        shares_outstanding = _DEFAULT_SHARES
        nav_per_share = nav / shares_outstanding if shares_outstanding > 0 else ZERO

        await self._nav_repo.upsert(
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            gross_market_value=gross_market_value,
            net_market_value=net_market_value,
            cash_balance=cash_balance,
            accrued_fees=accrued_fees,
            nav=nav,
            nav_per_share=nav_per_share,
            shares_outstanding=shares_outstanding,
            currency=currency,
            session=session,
        )

        result = NAVSnapshot(
            portfolio_id=portfolio_id,
            business_date=business_date,
            gross_market_value=gross_market_value,
            net_market_value=net_market_value,
            cash_balance=cash_balance,
            accrued_fees=accrued_fees,
            nav=nav,
            nav_per_share=nav_per_share,
            shares_outstanding=shares_outstanding,
            currency=currency,
            computed_at=datetime.now(UTC),
        )

        logger.info(
            "nav_calculated",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
            nav=str(nav),
        )
        return result
