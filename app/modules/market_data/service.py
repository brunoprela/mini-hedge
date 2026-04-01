"""Market data business logic — implements MarketDataReader protocol."""

from datetime import datetime

import structlog

from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.models import PriceRecord
from app.modules.market_data.repository import PriceRepository

logger = structlog.get_logger()


def _to_snapshot(record: PriceRecord) -> PriceSnapshot:
    return PriceSnapshot(
        instrument_id=record.instrument_id,
        bid=record.bid,
        ask=record.ask,
        mid=record.mid,
        volume=record.volume,
        timestamp=record.timestamp,
        source=record.source,
    )


class MarketDataService:
    """Implements MarketDataReader protocol."""

    def __init__(self, repository: PriceRepository) -> None:
        self._repo = repository
        # In-memory latest prices cache (updated by simulator events)
        self._latest: dict[str, PriceSnapshot] = {}

    def update_latest(self, snapshot: PriceSnapshot) -> None:
        """Called by event handler to keep in-memory cache current."""
        self._latest[snapshot.instrument_id] = snapshot

    async def get_latest_price(self, instrument_id: str) -> PriceSnapshot | None:
        # Check in-memory cache first
        cached = self._latest.get(instrument_id)
        if cached is not None:
            return cached
        # Fall back to database
        record = await self._repo.get_latest(instrument_id)
        if record is None:
            return None
        return _to_snapshot(record)

    async def get_price_history(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
    ) -> list[PriceSnapshot]:
        records = await self._repo.get_history(instrument_id, start, end)
        return [_to_snapshot(r) for r in records]

    async def store_price(self, snapshot: PriceSnapshot) -> None:
        """Persist a price snapshot to the database."""
        record = PriceRecord(
            timestamp=snapshot.timestamp,
            instrument_id=snapshot.instrument_id,
            bid=snapshot.bid,
            ask=snapshot.ask,
            mid=snapshot.mid,
            volume=snapshot.volume,
            source=snapshot.source,
        )
        await self._repo.insert(record)
