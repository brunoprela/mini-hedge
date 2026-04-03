"""Unit tests for the market data simulator."""

import pytest

from app.modules.market_data.simulator import InstrumentConfig, MarketDataSimulator
from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.schema_registry import shared_topic


class TestSimulator:
    def test_generate_tick_produces_positive_prices(self) -> None:
        bus = InProcessEventBus()
        sim = MarketDataSimulator(
            event_bus=bus,
            universe=[
                InstrumentConfig("TEST", 100.0, 0.10, 0.20, 10.0),
            ],
        )
        for _ in range(100):
            prices = sim._generate_tick()
            assert prices["TEST"] > 0

    @pytest.mark.asyncio
    async def test_publish_prices_emits_events(self) -> None:
        bus = InProcessEventBus()
        received: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received.append(event)

        bus.subscribe(shared_topic("prices.normalized"), handler)

        sim = MarketDataSimulator(
            event_bus=bus,
            universe=[
                InstrumentConfig("AAA", 100.0, 0.10, 0.20, 10.0),
                InstrumentConfig("BBB", 50.0, 0.05, 0.15, 8.0),
            ],
        )

        prices = sim._generate_tick()
        await sim._publish_prices(prices)

        assert len(received) == 2
        tickers = {e.data["instrument_id"] for e in received}
        assert tickers == {"AAA", "BBB"}

        for event in received:
            assert float(event.data["bid"]) < float(event.data["ask"])
            assert float(event.data["bid"]) <= float(event.data["mid"]) <= float(event.data["ask"])
