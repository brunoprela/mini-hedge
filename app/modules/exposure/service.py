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
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.modules.exposure.repository import ExposureRepository
    from app.modules.positions.service import PositionService
    from app.modules.security_master.service import (
        SecurityMasterService,
    )
    from app.shared.events import EventBus

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
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = exposure_repo
        self._positions = position_service
        self._sm = security_master_service
        self._event_bus = event_bus

    async def get_current(self, portfolio_id: UUID) -> PortfolioExposure:
        """Calculate current exposure from live positions."""
        positions = await self._positions.get_by_portfolio(portfolio_id)

        # Batch-fetch all instruments in one query instead of N+1
        instruments = await self._sm.get_all_active()
        instr_map = {i.ticker: i for i in instruments}

        position_values = []
        for pos in positions:
            if pos.quantity == ZERO:
                continue
            instrument = instr_map.get(pos.instrument_id)
            position_values.append(
                PositionValue(
                    instrument_id=pos.instrument_id,
                    quantity=pos.quantity,
                    market_price=pos.market_price,
                    market_value=pos.market_value,
                    asset_class=instrument.asset_class if instrument else None,
                    sector=getattr(instrument, "sector", None) if instrument else None,
                    country=getattr(instrument, "country", None) if instrument else None,
                    currency=pos.currency,
                )
            )
        return calculate_exposure(portfolio_id, position_values)

    async def get_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
        fund_slug: str | None = None,
    ) -> list[ExposureSnapshot]:
        """Return persisted exposure snapshots for a time range."""
        records = await self._repo.get_history(portfolio_id, start, end)
        return [
            ExposureSnapshot(
                id=r.id,
                portfolio_id=r.portfolio_id,
                fund_slug=fund_slug or "",
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

    async def take_snapshot(
        self,
        portfolio_id: UUID,
        fund_slug: str | None = None,
    ) -> None:
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
        await self._publish_exposure_event(exposure, fund_slug)
        logger.info(
            "exposure_snapshot_saved",
            portfolio_id=str(portfolio_id),
            gross=str(exposure.gross_exposure),
        )

    async def _publish_exposure_event(
        self,
        exposure: PortfolioExposure,
        fund_slug: str | None,
    ) -> None:
        """Publish an exposure.updated event to Kafka."""
        if self._event_bus is None or not fund_slug:
            return

        event = BaseEvent(
            event_type="exposure.updated",
            data={
                "portfolio_id": str(exposure.portfolio_id),
                "gross_exposure": str(exposure.gross_exposure),
                "net_exposure": str(exposure.net_exposure),
                "long_exposure": str(exposure.long_exposure),
                "short_exposure": str(exposure.short_exposure),
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "exposures.updated"),
            event,
        )
