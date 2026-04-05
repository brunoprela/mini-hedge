"""Tests for MarketDataService — price queries, spread calculation."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from mock_exchange.market_data.service import MarketDataService
from mock_exchange.market_data.simulator import GBMSimulator
from tests.factories import make_small_universe

if TYPE_CHECKING:
    from tests.conftest import FakeProducer


def _service_with_simulator(fake_producer: FakeProducer) -> MarketDataService:
    """Create a MarketDataService with a manually-wired simulator."""
    universe = make_small_universe()
    svc = MarketDataService()
    svc._universe = universe
    svc._simulator = GBMSimulator(
        producer=fake_producer,  # type: ignore[arg-type]
        universe=universe,
    )
    return svc


class TestGetLatestPrice:
    def test_no_simulator_returns_none(
        self, market_data_service: MarketDataService,
    ) -> None:
        assert market_data_service.get_latest_price("AAPL") is None

    def test_unknown_ticker_returns_none(
        self, fake_producer: FakeProducer,
    ) -> None:
        svc = _service_with_simulator(fake_producer)
        assert svc.get_latest_price("UNKNOWN") is None

    def test_returns_price_quote(self, fake_producer: FakeProducer) -> None:
        svc = _service_with_simulator(fake_producer)
        quote = svc.get_latest_price("TEST_TECH")
        assert quote is not None
        assert quote.instrument_id == "TEST_TECH"
        assert isinstance(quote.bid, Decimal)
        assert isinstance(quote.mid, Decimal)
        assert isinstance(quote.ask, Decimal)
        assert quote.bid < quote.mid < quote.ask

    def test_spread_calculation(self, fake_producer: FakeProducer) -> None:
        svc = _service_with_simulator(fake_producer)
        # TEST_TECH: initial_price=100.0, spread_bps=10.0
        quote = svc.get_latest_price("TEST_TECH")
        assert quote is not None
        spread = quote.ask - quote.bid
        expected_spread = Decimal("100.0") * Decimal("10.0") / Decimal("10000")
        # Allow small rounding difference
        assert abs(spread - expected_spread) < Decimal("0.01")


class TestGetAllPrices:
    def test_empty_without_simulator(
        self, market_data_service: MarketDataService,
    ) -> None:
        assert market_data_service.get_all_prices() == []

    def test_returns_all_instruments(self, fake_producer: FakeProducer) -> None:
        svc = _service_with_simulator(fake_producer)
        prices = svc.get_all_prices()
        assert len(prices) == 3
        tickers = {q.instrument_id for q in prices}
        assert tickers == {"TEST_TECH", "TEST_FIN", "TEST_NRG"}


class TestStopSimulator:
    def test_stop_without_start_does_not_raise(
        self, market_data_service: MarketDataService,
    ) -> None:
        market_data_service.stop_simulator()
