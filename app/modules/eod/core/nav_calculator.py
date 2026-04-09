"""NAV calculation — the single most important number a fund produces daily.

NAV = sum(position_market_values) + cash_balances - accrued_fees
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.eod.interfaces.snapshot import NAVSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.services import CapitalAccountService
    from app.modules.cash_management.services import CashManagementService
    from app.modules.eod.repositories import NAVSnapshotRepository
    from app.modules.fee_accounting.services import FeeAccountingService
    from app.modules.market_data.core.fx import FXConverter
    from app.modules.positions.services import PositionService

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
        fee_service: FeeAccountingService | None = None,
        capital_service: CapitalAccountService | None = None,
        fx_converter: FXConverter | None = None,
    ) -> None:
        self._positions = position_service
        self._cash = cash_service
        self._nav_repo = nav_repo
        self._fee_service = fee_service
        self._capital_service = capital_service
        self._fx = fx_converter

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

        gross_market_value = ZERO
        net_market_value = ZERO
        for p in positions:
            mv = self._to_base(p.market_value, p.currency, currency)
            gross_market_value += abs(mv)
            net_market_value += mv

        cash_balances = await self._cash.get_balances(portfolio_id, session=session)
        cash_balance = ZERO
        for b in cash_balances:
            cash_balance += self._to_base(b.total_balance, b.currency, currency)

        # Accrued fees from fee accounting (if wired)
        accrued_fees = ZERO
        if self._fee_service is not None:
            try:
                summary = await self._fee_service.get_fee_summary(portfolio_id, session=session)
                accrued_fees = Decimal(sum(summary.values())) if summary else ZERO
            except Exception:
                logger.warning("nav_fee_lookup_failed", portfolio_id=str(portfolio_id))

        nav = net_market_value + cash_balance - accrued_fees

        # Real shares outstanding from capital accounts (if wired)
        shares_outstanding = _DEFAULT_SHARES
        if self._capital_service is not None:
            try:
                real_shares = await self._capital_service.get_total_shares(session=session)
                if real_shares > ZERO:
                    shares_outstanding = real_shares
            except Exception:
                logger.warning("nav_shares_lookup_failed", portfolio_id=str(portfolio_id))
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

    def _to_base(self, amount: Decimal, from_ccy: str, base_ccy: str) -> Decimal:
        """Convert *amount* from *from_ccy* to *base_ccy* via FXConverter.

        Falls back to the unconverted amount if no rate is available (with a
        warning log), so NAV is never blocked by a missing FX rate.
        """
        if from_ccy == base_ccy or self._fx is None:
            return amount
        converted = self._fx.convert(amount, from_ccy, base_ccy)
        if converted is None:
            logger.warning(
                "nav_fx_conversion_fallback",
                from_ccy=from_ccy,
                base_ccy=base_ccy,
                amount=str(amount),
            )
            return amount
        return converted
