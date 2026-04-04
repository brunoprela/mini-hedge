"""Market data service — manages the GBM simulator and price state."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import structlog

from mock_exchange.shared.kafka import MockExchangeProducer
from mock_exchange.shared.models import PriceQuote

from .simulator import DEFAULT_UNIVERSE, GBMSimulator, InstrumentConfig

logger = structlog.get_logger()


class MarketDataService:
    """Manages the price simulator and provides REST-queryable price state."""

    def __init__(self) -> None:
        self._simulator: GBMSimulator | None = None
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._universe: list[InstrumentConfig] = list(DEFAULT_UNIVERSE)
        self._started_at: datetime | None = None

    async def start_simulator(
        self,
        interval_ms: int = 1000,
        kafka_bootstrap_servers: str = "localhost:9092",
        schema_registry_url: str = "http://localhost:8081",
    ) -> None:
        producer = MockExchangeProducer(bootstrap_servers=kafka_bootstrap_servers)
        self._simulator = GBMSimulator(
            producer=producer,
            universe=self._universe,
            interval_ms=interval_ms,
        )
        self._task = asyncio.create_task(self._simulator.run())
        self._started_at = datetime.now(UTC)
        logger.info("market_data_service_started", instruments=len(self._universe))

    def stop_simulator(self) -> None:
        if self._simulator:
            self._simulator.stop()
        if self._task:
            self._task.cancel()
        logger.info("market_data_service_stopped")

    @property
    def simulator(self) -> GBMSimulator | None:
        return self._simulator

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    def get_latest_price(self, ticker: str) -> PriceQuote | None:
        if not self._simulator:
            return None
        prices = self._simulator.current_prices
        if ticker not in prices:
            return None

        price = prices[ticker]
        cfg = next((c for c in self._universe if c.ticker == ticker), None)
        if cfg is None:
            return None

        spread = price * cfg.spread_bps / 10_000
        half_spread = spread / 2
        _q = Decimal("0.0001")
        mid = Decimal(str(price)).quantize(_q, rounding=ROUND_HALF_UP)
        bid = Decimal(str(price - half_spread)).quantize(_q, rounding=ROUND_HALF_UP)
        ask = Decimal(str(price + half_spread)).quantize(_q, rounding=ROUND_HALF_UP)

        return PriceQuote(
            instrument_id=ticker,
            bid=bid,
            ask=ask,
            mid=mid,
            volume=0,
            timestamp=datetime.now(UTC),
        )

    def get_all_prices(self) -> list[PriceQuote]:
        return [
            quote
            for cfg in self._universe
            if (quote := self.get_latest_price(cfg.ticker)) is not None
        ]
