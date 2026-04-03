"""Exposure service — calculates and persists exposure snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.exposure.calculator import calculate_exposure
from app.modules.exposure.interface import (
    ExposureSnapshot,
    PortfolioExposure,
    PositionValue,
)
from app.modules.exposure.models import ExposureSnapshotRecord

if TYPE_CHECKING:
    from app.modules.exposure.repository import ExposureRepository
    from app.modules.positions.service import PositionService
    from app.modules.security_master.service import (
        SecurityMasterService,
    )

logger = structlog.get_logger()

ZERO = Decimal(0)


class ExposureService:
    """Calculates portfolio exposure from current positions."""

    def __init__(
        self,
        *,
        exposure_repo: ExposureRepository,
        position_service: PositionService,
        security_master_service: SecurityMasterService,
    ) -> None:
        self._repo = exposure_repo
        self._positions = position_service
        self._sm = security_master_service

    async def get_current(self, portfolio_id: UUID) -> PortfolioExposure:
        """Calculate current exposure from live positions."""
        positions = await self._positions.get_by_portfolio(portfolio_id)
        position_values = []
        for pos in positions:
            if pos.quantity == ZERO:
                continue
            # Look up instrument metadata
            asset_class = None
            sector = None
            country = None
            try:
                instrument = await self._sm.get_by_ticker(pos.instrument_id)
                asset_class = instrument.asset_class
                sector = getattr(instrument, "sector", None)
                country = getattr(instrument, "country", None)
            except Exception:
                pass
            position_values.append(
                PositionValue(
                    instrument_id=pos.instrument_id,
                    quantity=pos.quantity,
                    market_price=pos.market_price,
                    market_value=pos.market_value,
                    asset_class=asset_class,
                    sector=sector,
                    country=country,
                    currency=pos.currency,
                )
            )
        return calculate_exposure(portfolio_id, position_values)

    async def get_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
        fund_slug: str = "",
    ) -> list[ExposureSnapshot]:
        """Return persisted exposure snapshots for a time range."""
        records = await self._repo.get_history(portfolio_id, start, end)
        return [
            ExposureSnapshot(
                id=r.id,
                portfolio_id=r.portfolio_id,
                fund_slug=fund_slug,
                gross_exposure=r.gross_exposure,
                net_exposure=r.net_exposure,
                long_exposure=r.long_exposure,
                short_exposure=r.short_exposure,
                long_count=r.long_count,
                short_count=r.short_count,
                snapshot_at=r.snapshot_at,
            )
            for r in records
        ]

    async def take_snapshot(self, portfolio_id: UUID) -> None:
        """Calculate and persist an exposure snapshot."""
        exposure = await self.get_current(portfolio_id)
        # Serialize breakdowns to JSON-compatible dict
        breakdowns_json: dict[str, list[dict[str, str]]] = {}
        for dim_key, items in exposure.breakdowns.items():
            breakdowns_json[dim_key] = [
                {
                    "dimension": item.dimension,
                    "key": item.key,
                    "long_value": str(item.long_value),
                    "short_value": str(item.short_value),
                    "net_value": str(item.net_value),
                    "gross_value": str(item.gross_value),
                    "weight_pct": str(item.weight_pct),
                }
                for item in items
            ]
        record = ExposureSnapshotRecord(
            portfolio_id=str(portfolio_id),
            gross_exposure=exposure.gross_exposure,
            net_exposure=exposure.net_exposure,
            long_exposure=exposure.long_exposure,
            short_exposure=exposure.short_exposure,
            long_count=exposure.long_count,
            short_count=exposure.short_count,
            breakdowns=breakdowns_json,
            snapshot_at=exposure.calculated_at,
        )
        await self._repo.save_snapshot(record)
        logger.info(
            "exposure_snapshot_saved",
            portfolio_id=str(portfolio_id),
            gross=str(exposure.gross_exposure),
        )
