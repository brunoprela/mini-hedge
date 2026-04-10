"""VWAP calculator — computes volume-weighted average price from price history."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.modules.market_data.services import MarketDataService

logger = structlog.get_logger()

_ZERO = Decimal("0")


class VWAPCalculator:
    """Compute VWAP from 1-min bar snapshots stored in market_data.prices."""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data = market_data_service

    async def compute(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
    ) -> Decimal | None:
        """Compute VWAP over [start, end] from stored price bars.

        Returns None if no bars with volume data exist in the window.
        VWAP = sum(mid * volume) / sum(volume) across all bars.
        """
        snapshots = await self._market_data.get_price_history(instrument_id, start, end)

        if not snapshots:
            logger.debug(
                "vwap_no_bars",
                instrument_id=instrument_id,
                start=start.isoformat(),
                end=end.isoformat(),
            )
            return None

        total_pv = _ZERO
        total_volume = _ZERO

        for snap in snapshots:
            vol = snap.volume or _ZERO
            if vol > _ZERO:
                total_pv += snap.mid * vol
                total_volume += vol

        if total_volume <= _ZERO:
            # All bars had zero/null volume — fall back to simple average of mids
            mids = [s.mid for s in snapshots if s.mid > _ZERO]
            if not mids:
                return None
            return sum(mids, _ZERO) / len(mids)

        return (total_pv / total_volume).quantize(Decimal("0.00000001"))
