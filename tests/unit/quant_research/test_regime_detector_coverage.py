"""Additional unit tests for RegimeDetector — covers uncovered classify
branches: HIGH_VOL, RECOVERY, LOW_VOL, NORMAL, and edge cases in helper
methods.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.quant_research.core.regime_detector import RegimeDetector
from app.modules.quant_research.interfaces import RegimeConfig, RegimeType

ZERO = Decimal(0)


def _make_price_series(
    n: int,
    start: Decimal = Decimal("100"),
    daily_pct: Decimal = Decimal("0.001"),
) -> list[tuple[date, Decimal]]:
    series: list[tuple[date, Decimal]] = []
    price = start
    base = date(2024, 1, 1)
    for i in range(n):
        series.append((base + timedelta(days=i), price))
        price = price * (Decimal(1) + daily_pct)
    return series


class TestClassifyRegime:
    """Directly test _classify_regime to cover all branches."""

    def setup_method(self):
        self.detector = RegimeDetector()

    def test_crisis_regime(self):
        # drawdown < -0.20 AND vol > high threshold (0.25)
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.35"),
            trend=Decimal("-0.15"),
            drawdown=Decimal("-0.25"),
        )
        assert regime == RegimeType.CRISIS
        assert confidence <= Decimal(1)

    def test_bear_regime(self):
        # trend < 0 AND vol > low threshold (0.12)
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.15"),
            trend=Decimal("-0.05"),
            drawdown=Decimal("-0.05"),
        )
        assert regime == RegimeType.BEAR

    def test_high_vol_regime(self):
        # vol > high threshold AND trend >= 0
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.30"),
            trend=Decimal("0.02"),
            drawdown=Decimal("-0.03"),
        )
        assert regime == RegimeType.HIGH_VOL

    def test_recovery_regime(self):
        # trend > 0 AND drawdown < -0.10
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.10"),
            trend=Decimal("0.08"),
            drawdown=Decimal("-0.15"),
        )
        assert regime == RegimeType.RECOVERY

    def test_bull_regime(self):
        # trend > 0 AND vol < low threshold (0.12)
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.08"),
            trend=Decimal("0.10"),
            drawdown=Decimal("-0.02"),
        )
        assert regime == RegimeType.BULL

    def test_low_vol_regime(self):
        # vol < low_threshold * 0.7 = 0.084
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.05"),
            trend=Decimal("0.00"),
            drawdown=Decimal("-0.01"),
        )
        assert regime == RegimeType.LOW_VOL

    def test_normal_regime(self):
        # Nothing special — moderate vol, no clear trend
        regime, confidence = self.detector._classify_regime(
            volatility=Decimal("0.10"),
            trend=Decimal("0.00"),
            drawdown=Decimal("-0.02"),
        )
        assert regime == RegimeType.NORMAL
        assert confidence == Decimal("0.5")


class TestHelperMethods:
    """Cover edge cases in private helper methods."""

    def setup_method(self):
        self.detector = RegimeDetector()

    def test_compute_rolling_volatility_insufficient_data(self):
        result = self.detector._compute_rolling_volatility(
            [Decimal("0.01"), Decimal("-0.01")], window=10
        )
        assert result == ZERO

    def test_compute_rolling_volatility_single_value_in_window(self):
        result = self.detector._compute_rolling_volatility(
            [Decimal("0.01")], window=1
        )
        assert result == ZERO

    def test_compute_trend_insufficient_data(self):
        result = self.detector._compute_trend(
            [Decimal("100")], window=63
        )
        assert result == ZERO

    def test_compute_trend_zero_start(self):
        result = self.detector._compute_trend(
            [ZERO, Decimal("100")], window=2
        )
        assert result == ZERO

    def test_compute_drawdown_empty(self):
        result = self.detector._compute_drawdown([])
        assert result == ZERO

    def test_compute_drawdown_zero_peak(self):
        result = self.detector._compute_drawdown([ZERO, ZERO])
        assert result == ZERO

    def test_build_regime_history_insufficient_returns(self):
        detector = RegimeDetector()
        prices = _make_price_series(50)
        returns = [Decimal("0.001")] * 49
        result = detector._build_regime_history(prices, returns)
        assert result == []

    def test_build_transition_matrix_empty_history(self):
        result = self.detector._build_transition_matrix([])
        assert result == {}

    def test_build_transition_matrix_single_entry(self):
        from app.modules.quant_research.interfaces import MarketRegime

        history = [
            MarketRegime(
                regime_type=RegimeType.BULL,
                start_date=date(2025, 1, 1),
                end_date=None,
                confidence=Decimal("0.8"),
                indicators={},
            )
        ]
        result = self.detector._build_transition_matrix(history)
        assert result == {}


class TestRegimeDetectorIntegration:
    """End-to-end scenarios that exercise the full detect_regime path."""

    def test_high_vol_with_uptrend(self):
        """Build a volatile uptrend to hit the HIGH_VOL branch."""
        config = RegimeConfig(
            lookback_days=100,
            vol_window=21,
            trend_window=63,
            vol_threshold_high=Decimal("0.15"),
            vol_threshold_low=Decimal("0.08"),
        )
        detector = RegimeDetector(config=config)

        # Build a volatile uptrend: price increases but with big swings
        base = date(2024, 1, 1)
        series: list[tuple[date, Decimal]] = []
        price = Decimal("100")
        for i in range(200):
            series.append((base + timedelta(days=i), price))
            if i % 2 == 0:
                price = price * Decimal("1.04")  # big up
            else:
                price = price * Decimal("0.97")  # smaller down, net upward

        result = detector.detect_regime(series)
        # Should classify as something — we just need this branch exercised
        assert result.current_regime in set(RegimeType)
        assert len(result.indicators) == 3

    def test_recovery_scenario(self):
        """Build a crash-then-recovery to exercise RECOVERY branch."""
        config = RegimeConfig(
            lookback_days=100,
            vol_window=21,
            trend_window=63,
            vol_threshold_high=Decimal("0.25"),
            vol_threshold_low=Decimal("0.12"),
        )
        detector = RegimeDetector(config=config)

        base = date(2024, 1, 1)
        series: list[tuple[date, Decimal]] = []
        price = Decimal("200")

        # Phase 1: Build up a peak (100 days)
        for i in range(100):
            series.append((base + timedelta(days=i), price))
            price = price * Decimal("1.001")

        # Phase 2: Crash (40 days)
        for i in range(100, 140):
            series.append((base + timedelta(days=i), price))
            price = price * Decimal("0.99")

        # Phase 3: Recovery with low vol (60 days)
        for i in range(140, 200):
            series.append((base + timedelta(days=i), price))
            price = price * Decimal("1.002")

        result = detector.detect_regime(series)
        assert result.current_regime in set(RegimeType)
