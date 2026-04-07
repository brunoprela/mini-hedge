"""P&L snapshot — freezes daily realized + unrealized P&L per portfolio.

The snapshot is immutable after EOD — it becomes the basis for performance
reporting and fee calculations.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.eod.interface import PnLSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.eod.repository import PnLSnapshotRepository
    from app.modules.market_data.fx import FXConverter
    from app.modules.positions.service import PositionService

logger = structlog.get_logger()

ZERO = Decimal(0)


class PnLSnapshotService:
    """Captures and freezes daily P&L for a portfolio."""

    def __init__(
        self,
        *,
        position_service: PositionService,
        pnl_repo: PnLSnapshotRepository,
        fx_converter: FXConverter | None = None,
    ) -> None:
        self._positions = position_service
        self._pnl_repo = pnl_repo
        self._fx = fx_converter

    async def snapshot_pnl(
        self,
        portfolio_id: UUID,
        business_date: date,
        *,
        base_currency: str = "USD",
        session: AsyncSession | None = None,
    ) -> PnLSnapshot:
        """Freeze daily P&L from current position state."""
        positions = await self._positions.get_by_portfolio(portfolio_id, session=session)

        total_unrealized = ZERO
        total_realized = ZERO
        for p in positions:
            total_unrealized += self._to_base(p.unrealized_pnl, p.currency, base_currency)
        total_pnl = total_realized + total_unrealized

        details = [
            {
                "instrument_id": p.instrument_id,
                "quantity": str(p.quantity),
                "market_value": str(p.market_value),
                "unrealized_pnl": str(p.unrealized_pnl),
                "cost_basis": str(p.cost_basis),
                "currency": p.currency,
            }
            for p in positions
        ]

        await self._pnl_repo.upsert(
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            total_realized_pnl=total_realized,
            total_unrealized_pnl=total_unrealized,
            total_pnl=total_pnl,
            position_count=len(positions),
            details={"positions": details},
            session=session,
        )

        result = PnLSnapshot(
            portfolio_id=portfolio_id,
            business_date=business_date,
            total_realized_pnl=total_realized,
            total_unrealized_pnl=total_unrealized,
            total_pnl=total_pnl,
            position_count=len(positions),
            computed_at=datetime.now(UTC),
        )

        logger.info(
            "pnl_snapshot_taken",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
            total_pnl=str(total_pnl),
        )
        return result

    def _to_base(self, amount: Decimal, from_ccy: str, base_ccy: str) -> Decimal:
        """Convert amount to base currency, falling back to unconverted."""
        if from_ccy == base_ccy or self._fx is None:
            return amount
        converted = self._fx.convert(amount, from_ccy, base_ccy)
        if converted is None:
            logger.warning(
                "pnl_fx_conversion_fallback",
                from_ccy=from_ccy,
                base_ccy=base_ccy,
            )
            return amount
        return converted
