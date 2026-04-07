"""Market data service — manages the GBM simulator, order books, and trade tape."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

import structlog

from mock_exchange.market_data.ambient_flow import AmbientFlowGenerator
from mock_exchange.market_data.order_book import SimulatedOrderBook
from mock_exchange.market_data.trade_tape import TradeTape
from mock_exchange.market_data.volume_profile import DEFAULT_PROFILE
from mock_exchange.reference_data.instruments import INSTRUMENT_UNIVERSE
from mock_exchange.shared.kafka import MockExchangeProducer
from mock_exchange.shared.models import InstrumentInfo, OrderBookSnapshot, PriceQuote, VWAPData

from .simulator import DEFAULT_UNIVERSE, GBMSimulator, InstrumentConfig

if TYPE_CHECKING:
    from mock_exchange.market_data.volume_profile import IntradayVolumeProfile

logger = structlog.get_logger()


class MarketDataService:
    """Manages the price simulator, order books, ambient flow, and trade tape."""

    def __init__(self) -> None:
        self._simulator: GBMSimulator | None = None
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._universe: list[InstrumentConfig] = list(DEFAULT_UNIVERSE)
        self._started_at: datetime | None = None

        # Order book and trade infrastructure
        self._order_books: dict[str, SimulatedOrderBook] = {}
        self._trade_tape: TradeTape | None = None
        self._ambient_flow: AmbientFlowGenerator | None = None
        self._volume_profile: IntradayVolumeProfile = DEFAULT_PROFILE

        # Build instrument lookup from reference data
        self._instruments: dict[str, InstrumentInfo] = {
            i.ticker: i for i in INSTRUMENT_UNIVERSE
        }

    async def start_simulator(
        self,
        interval_ms: int = 1000,
        kafka_bootstrap_servers: str = "localhost:9092",
        schema_registry_url: str = "http://localhost:8081",
        ambient_flow_enabled: bool = True,
        ambient_flow_interval_ms: int = 1000,
    ) -> None:
        producer = MockExchangeProducer(bootstrap_servers=kafka_bootstrap_servers)

        # Initialize order books for all instruments
        self._order_books = {}
        for instrument in INSTRUMENT_UNIVERSE:
            self._order_books[instrument.ticker] = SimulatedOrderBook(
                instrument_id=instrument.ticker,
                tick_size=instrument.tick_size,
                spread_bps=instrument.spread_bps,
                avg_daily_volume=instrument.avg_daily_volume,
            )

        # Initialize trade tape
        self._trade_tape = TradeTape(producer=producer)

        # Start GBM simulator
        self._simulator = GBMSimulator(
            producer=producer,
            universe=self._universe,
            interval_ms=interval_ms,
            order_books=self._order_books,
            trade_tape=self._trade_tape,
        )
        self._task = asyncio.create_task(self._simulator.run())
        self._started_at = datetime.now(UTC)

        # Start ambient flow generator
        if ambient_flow_enabled:
            self._ambient_flow = AmbientFlowGenerator(
                order_books=self._order_books,
                instruments=self._instruments,
                volume_profile=self._volume_profile,
                trade_tape=self._trade_tape,
                interval_ms=ambient_flow_interval_ms,
            )
            await self._ambient_flow.start()

        logger.info(
            "market_data_service_started",
            instruments=len(self._universe),
            order_books=len(self._order_books),
            ambient_flow=ambient_flow_enabled,
        )

    def stop_simulator(self) -> None:
        if self._ambient_flow:
            asyncio.create_task(self._ambient_flow.stop())
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

    @property
    def order_books(self) -> dict[str, SimulatedOrderBook]:
        return self._order_books

    @property
    def trade_tape(self) -> TradeTape | None:
        return self._trade_tape

    @property
    def instruments(self) -> dict[str, InstrumentInfo]:
        return self._instruments

    def get_latest_price(self, ticker: str) -> PriceQuote | None:
        """Get latest price — prefer order book, fallback to GBM."""
        book = self._order_books.get(ticker)
        if book:
            bb = book.best_bid
            ba = book.best_ask
            if bb is not None and ba is not None:
                _q = Decimal("0.0001")
                return PriceQuote(
                    instrument_id=ticker,
                    bid=bb.quantize(_q),
                    ask=ba.quantize(_q),
                    mid=book.mid.quantize(_q),
                    volume=self._trade_tape.daily_volume(ticker) if self._trade_tape else 0,
                    timestamp=datetime.now(UTC),
                )

        # Fallback to GBM simulator
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
            volume=self._trade_tape.daily_volume(ticker) if self._trade_tape else 0,
            timestamp=datetime.now(UTC),
        )

    def get_all_prices(self) -> list[PriceQuote]:
        return [
            quote
            for cfg in self._universe
            if (quote := self.get_latest_price(cfg.ticker)) is not None
        ]

    def get_order_book_snapshot(self, ticker: str, depth: int = 5) -> OrderBookSnapshot | None:
        book = self._order_books.get(ticker)
        if not book:
            return None
        return book.snapshot(depth=depth)

    def get_vwap(self, ticker: str, start: datetime, end: datetime) -> VWAPData | None:
        if not self._trade_tape:
            return None
        return self._trade_tape.vwap(ticker, start, end)
