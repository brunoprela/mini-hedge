"""Market data business logic — implements MarketDataReader protocol."""

from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.core.fx import FXConverter
from app.modules.market_data.interfaces import FXRateSnapshot, OHLCVBar, PriceSnapshot
from app.modules.market_data.models.fx_rate import FXRateRecord
from app.modules.market_data.models.price import PriceRecord
from app.modules.market_data.repositories import FXRateRepository, PriceRepository

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


def _to_fx_snapshot(record: FXRateRecord) -> FXRateSnapshot:
    return FXRateSnapshot(
        base_currency=record.base_currency,
        quote_currency=record.quote_currency,
        rate=record.rate,
        timestamp=record.timestamp,
        source=record.source,
    )


class MarketDataService:
    """Implements MarketDataReader protocol."""

    def __init__(
        self,
        *,
        price_repo: PriceRepository,
        fx_repo: FXRateRepository,
    ) -> None:
        self._price_repo = price_repo
        self._fx_repo = fx_repo
        self._fx_converter = FXConverter()
        # In-memory latest prices cache (updated by simulator events)
        self._latest: dict[str, PriceSnapshot] = {}

    def update_latest(self, snapshot: PriceSnapshot) -> None:
        """Called by event handler to keep in-memory cache current."""
        self._latest[snapshot.instrument_id] = snapshot

    async def get_latest_price(
        self, instrument_id: str, *, session: AsyncSession | None = None
    ) -> PriceSnapshot | None:
        # Check in-memory cache first
        cached = self._latest.get(instrument_id)
        if cached is not None:
            return cached
        # Fall back to database
        record = await self._price_repo.get_latest(instrument_id, session=session)
        if record is None:
            return None
        return _to_snapshot(record)

    async def get_price_history(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[PriceSnapshot]:
        records = await self._price_repo.get_history(instrument_id, start, end, session=session)
        return [_to_snapshot(r) for r in records]

    async def store_price(
        self, snapshot: PriceSnapshot, *, session: AsyncSession | None = None
    ) -> None:
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
        await self._price_repo.insert(record, session=session)

    async def get_ohlcv_bars(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
        interval: str = "1 day",
        *,
        session: AsyncSession | None = None,
    ) -> list[OHLCVBar]:
        """Return OHLCV bars aggregated from raw price ticks."""
        rows = await self._price_repo.get_ohlcv_bars(
            instrument_id, start, end, interval, session=session
        )
        return [
            OHLCVBar(
                instrument_id=instrument_id,
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                period_start=row["period_start"],
                period_end=row["period_end"],
                source="aggregated",
            )
            for row in rows
        ]

    # ── FX rates ──────────────────────────────────────────────

    def update_fx_rate(self, snapshot: FXRateSnapshot) -> None:
        """Update the in-memory FX converter cache."""
        self._fx_converter.update_rate(
            snapshot.base_currency, snapshot.quote_currency, snapshot.rate
        )
        logger.debug(
            "fx_rate_updated",
            pair=f"{snapshot.base_currency}/{snapshot.quote_currency}",
            rate=str(snapshot.rate),
        )

    async def store_fx_rate(
        self, snapshot: FXRateSnapshot, *, session: AsyncSession | None = None
    ) -> None:
        """Persist an FX rate snapshot to the database."""
        record = FXRateRecord(
            timestamp=snapshot.timestamp,
            base_currency=snapshot.base_currency,
            quote_currency=snapshot.quote_currency,
            rate=snapshot.rate,
            source=snapshot.source,
        )
        await self._fx_repo.insert(record, session=session)

    async def get_fx_rate(
        self,
        base_currency: str,
        quote_currency: str,
        *,
        session: AsyncSession | None = None,
    ) -> FXRateSnapshot | None:
        """Get the latest FX rate for a currency pair."""
        record = await self._fx_repo.get_latest(base_currency, quote_currency, session=session)
        if record is None:
            return None
        return _to_fx_snapshot(record)

    async def get_all_fx_rates(
        self, *, session: AsyncSession | None = None
    ) -> list[FXRateSnapshot]:
        """Get the latest rate for every stored currency pair."""
        records = await self._fx_repo.get_latest_all(session=session)
        return [_to_fx_snapshot(r) for r in records]

    @property
    def fx_converter(self) -> FXConverter:
        """Expose the in-memory FX converter for downstream consumers."""
        return self._fx_converter
