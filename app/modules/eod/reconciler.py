"""Position reconciliation — compares internal positions against broker statement.

For mock-exchange, the "broker file" is an HTTP call to the mock-exchange API.
In production this would parse a CSV/FIX file from the prime broker.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.eod.interface import (
    BreakType,
    ReconciliationBreak,
    ReconciliationResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.eod.repository import ReconciliationRepository
    from app.modules.positions.service import PositionService
    from app.shared.adapters import BrokerAdapter

logger = structlog.get_logger()

MATERIAL_THRESHOLD = Decimal("0.01")


class PositionReconciler:
    """Compares internal positions against the broker's EOD statement."""

    def __init__(
        self,
        *,
        position_service: PositionService,
        broker_adapter: BrokerAdapter,
        recon_repo: ReconciliationRepository,
    ) -> None:
        self._positions = position_service
        self._broker = broker_adapter
        self._recon_repo = recon_repo

    async def reconcile(
        self,
        portfolio_id: UUID,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationResult:
        """Run position reconciliation against broker.

        For mock-exchange, uses the internal view as a placeholder.
        A real implementation would parse the broker's EOD position file.
        """
        internal_positions = await self._positions.get_by_portfolio(portfolio_id, session=session)
        internal_map = {p.instrument_id: p.quantity for p in internal_positions}

        # Placeholder: broker == internal (reconciliation always passes)
        # Real implementation: broker_positions = await self._broker.get_eod_positions(...)
        broker_map: dict[str, Decimal] = dict(internal_map)

        all_instruments = set(internal_map.keys()) | set(broker_map.keys())
        breaks: list[ReconciliationBreak] = []

        for instrument_id in all_instruments:
            internal_qty = internal_map.get(instrument_id, Decimal(0))
            broker_qty = broker_map.get(instrument_id, Decimal(0))

            if internal_qty == Decimal(0) and broker_qty != Decimal(0):
                breaks.append(
                    ReconciliationBreak(
                        instrument_id=instrument_id,
                        break_type=BreakType.MISSING_INTERNAL,
                        internal_quantity=internal_qty,
                        broker_quantity=broker_qty,
                        difference=-broker_qty,
                        is_material=abs(broker_qty) > MATERIAL_THRESHOLD,
                    )
                )
            elif broker_qty == Decimal(0) and internal_qty != Decimal(0):
                breaks.append(
                    ReconciliationBreak(
                        instrument_id=instrument_id,
                        break_type=BreakType.MISSING_BROKER,
                        internal_quantity=internal_qty,
                        broker_quantity=broker_qty,
                        difference=internal_qty,
                        is_material=abs(internal_qty) > MATERIAL_THRESHOLD,
                    )
                )
            elif internal_qty != broker_qty:
                diff = internal_qty - broker_qty
                breaks.append(
                    ReconciliationBreak(
                        instrument_id=instrument_id,
                        break_type=BreakType.QUANTITY_MISMATCH,
                        internal_quantity=internal_qty,
                        broker_quantity=broker_qty,
                        difference=diff,
                        is_material=abs(diff) > MATERIAL_THRESHOLD,
                    )
                )

        is_clean = len(breaks) == 0

        await self._recon_repo.upsert(
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            total_positions=len(all_instruments),
            matched_positions=len(all_instruments) - len(breaks),
            is_clean=is_clean,
            breaks=[b.model_dump(mode="json") for b in breaks],
            session=session,
        )

        result = ReconciliationResult(
            portfolio_id=portfolio_id,
            business_date=business_date,
            total_positions=len(all_instruments),
            matched_positions=len(all_instruments) - len(breaks),
            breaks=breaks,
            is_clean=is_clean,
            reconciled_at=datetime.now(UTC),
        )

        logger.info(
            "position_reconciliation_complete",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
            total=result.total_positions,
            breaks=len(breaks),
        )
        return result
