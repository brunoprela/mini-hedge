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
    ) -> None:
        self._positions = position_service
        self._pnl_repo = pnl_repo

    async def snapshot_pnl(
        self,
        portfolio_id: UUID,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> PnLSnapshot:
        """Freeze daily P&L from current position state."""
        positions = await self._positions.get_by_portfolio(portfolio_id, session=session)

        total_unrealized = sum(p.unrealized_pnl for p in positions) if positions else ZERO
        total_realized = ZERO
        total_pnl = total_realized + total_unrealized

        details = [
            {
                "instrument_id": p.instrument_id,
                "quantity": str(p.quantity),
                "market_value": str(p.market_value),
                "unrealized_pnl": str(p.unrealized_pnl),
                "cost_basis": str(p.cost_basis),
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
            details=details,
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
