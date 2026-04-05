"""Price finalization — captures and locks closing prices for a business date.

After finalization, all mark-to-market for the business date uses the locked
closing price, not any subsequent real-time price.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import structlog

from app.modules.eod.interface import FinalizedPrice, PriceFinalizationResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.eod.repository import FinalizedPriceRepository
    from app.modules.market_data.service import MarketDataService
    from app.modules.security_master.service import SecurityMasterService

logger = structlog.get_logger()


class PriceFinalizationService:
    """Captures closing prices from market data and locks them for EOD."""

    def __init__(
        self,
        *,
        price_repo: FinalizedPriceRepository,
        market_data_service: MarketDataService,
        security_master_service: SecurityMasterService,
    ) -> None:
        self._price_repo = price_repo
        self._market_data = market_data_service
        self._sm = security_master_service

    async def finalize_prices(
        self,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> PriceFinalizationResult:
        """Lock closing prices for all active instruments.

        Reads the latest price from market data for each instrument in the
        security master and writes it to ``eod.finalized_prices``.
        """
        instruments = await self._sm.get_all_active(session=session)
        finalized: list[FinalizedPrice] = []
        missing: list[str] = []

        for inst in instruments:
            price_snap = await self._market_data.get_latest_price(
                inst.instrument_id, session=session
            )
            if price_snap is None or price_snap.mid_price is None:
                missing.append(inst.ticker)
                continue

            await self._price_repo.upsert_price(
                instrument_id=inst.instrument_id,
                business_date=business_date,
                close_price=price_snap.mid_price,
                source="market_data",
                finalized_by="eod_orchestrator",
                session=session,
            )
            finalized.append(
                FinalizedPrice(
                    instrument_id=inst.instrument_id,
                    business_date=business_date,
                    close_price=price_snap.mid_price,
                    source="market_data",
                    finalized_at=datetime.now(UTC),
                    finalized_by="eod_orchestrator",
                )
            )

        result = PriceFinalizationResult(
            business_date=business_date,
            total_instruments=len(instruments),
            finalized_count=len(finalized),
            missing_count=len(missing),
            missing_instruments=missing,
            is_complete=len(missing) == 0,
        )

        logger.info(
            "prices_finalized",
            business_date=str(business_date),
            finalized=result.finalized_count,
            missing=result.missing_count,
        )
        return result
