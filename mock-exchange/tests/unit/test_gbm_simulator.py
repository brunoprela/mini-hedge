"""Tests for GBMSimulator — tick generation, correlation, regime, publishing."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import numpy as np

from mock_exchange.market_data.simulator import (
    CROSS_SECTOR_CORR,
    INTRA_SECTOR_CORR,
    SECTOR_GROUPS,
    GBMSimulator,
    _build_correlation_matrix,
)
from tests.factories import make_small_universe

if TYPE_CHECKING:
    from tests.conftest import FakeProducer


class TestInitialState:
    def test_initial_prices_match_config(self, gbm_simulator: GBMSimulator) -> None:
        universe = make_small_universe()
        for cfg in universe:
            assert gbm_simulator.current_prices[cfg.ticker] == cfg.initial_price

    def test_stop_sets_running_false(self, gbm_simulator: GBMSimulator) -> None:
        gbm_simulator._running = True
        gbm_simulator.stop()
        assert gbm_simulator._running is False


class TestTickGeneration:
    def test_returns_all_instruments(self, gbm_simulator: GBMSimulator) -> None:
        prices = gbm_simulator._generate_tick()
        assert set(prices.keys()) == {"TEST_TECH", "TEST_FIN", "TEST_NRG"}

    def test_prices_stay_positive(self, gbm_simulator: GBMSimulator) -> None:
        np.random.seed(42)
        for _ in range(1000):
            prices = gbm_simulator._generate_tick()
            for price in prices.values():
                assert price > 0, f"Price went non-positive: {price}"

    def test_prices_change(self, gbm_simulator: GBMSimulator) -> None:
        np.random.seed(123)
        initial = dict(gbm_simulator.current_prices)
        gbm_simulator._generate_tick()
        current = gbm_simulator.current_prices
        assert any(
            current[t] != initial[t] for t in initial
        ), "Prices should change after a tick"


class TestPublishPrices:
    def test_produces_messages(
        self,
        fake_producer: FakeProducer,
        gbm_simulator: GBMSimulator,
    ) -> None:
        prices = gbm_simulator._generate_tick()
        gbm_simulator._publish_prices(prices)
        assert len(fake_producer.messages) == 3
        for msg in fake_producer.messages:
            assert msg["topic"] == "shared.prices.normalized"
            assert msg["event_type"] == "price.updated"

    def test_price_data_format(
        self,
        fake_producer: FakeProducer,
        gbm_simulator: GBMSimulator,
    ) -> None:
        prices = gbm_simulator._generate_tick()
        gbm_simulator._publish_prices(prices)
        for msg in fake_producer.messages:
            data = msg["data"]
            assert "instrument_id" in data
            assert "bid" in data
            assert "ask" in data
            assert "mid" in data
            assert "volume" in data
            assert "timestamp" in data
            assert data["source"] == "mock-exchange"
            # bid <= mid <= ask
            bid = Decimal(data["bid"])
            mid = Decimal(data["mid"])
            ask = Decimal(data["ask"])
            assert bid <= mid <= ask


class TestRegime:
    def test_apply_regime(self, gbm_simulator: GBMSimulator) -> None:
        gbm_simulator.apply_regime(
            drift_mult=2.0, vol_mult=3.0, corr_boost=0.1,
        )
        assert gbm_simulator.drift_multiplier == 2.0
        assert gbm_simulator.volatility_multiplier == 3.0
        assert gbm_simulator.correlation_boost == 0.1

    def test_reset_regime(self, gbm_simulator: GBMSimulator) -> None:
        gbm_simulator.apply_regime(2.0, 3.0, 0.1)
        gbm_simulator.reset_regime()
        assert gbm_simulator.drift_multiplier == 1.0
        assert gbm_simulator.volatility_multiplier == 1.0
        assert gbm_simulator.correlation_boost == 0.0

    def test_cholesky_rebuilt_on_regime_change(
        self, gbm_simulator: GBMSimulator,
    ) -> None:
        before = gbm_simulator._cholesky.copy()  # type: ignore[union-attr]
        gbm_simulator.apply_regime(1.0, 1.0, 0.2)
        assert not np.array_equal(before, gbm_simulator._cholesky)


class TestCorrelationMatrix:
    def test_structure(self) -> None:
        n = 42
        corr = _build_correlation_matrix(n)
        assert corr.shape == (n, n)
        # Diagonal is 1.0
        np.testing.assert_array_equal(np.diag(corr), np.ones(n))
        # Symmetric
        np.testing.assert_array_equal(corr, corr.T)

    def test_intra_sector_correlation(self) -> None:
        corr = _build_correlation_matrix(42)
        # Check first tech sector pair (indices 0, 1)
        assert corr[0, 1] == INTRA_SECTOR_CORR

    def test_cross_sector_correlation(self) -> None:
        corr = _build_correlation_matrix(42)
        # Index 0 (tech) vs index 8 (financials)
        assert corr[0, 8] == CROSS_SECTOR_CORR

    def test_positive_definite(self) -> None:
        corr = _build_correlation_matrix(42)
        eigenvalues = np.linalg.eigvalsh(corr)
        assert np.all(eigenvalues > 0), (
            f"Matrix not positive definite: min eigenvalue={eigenvalues.min()}"
        )

    def test_sector_groups_cover_all_instruments(self) -> None:
        all_indices = set()
        for group in SECTOR_GROUPS:
            all_indices.update(group)
        assert all_indices == set(range(42))
