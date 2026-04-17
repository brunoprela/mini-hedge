"""Market regime detection using statistical methods."""

from __future__ import annotations

import statistics
from datetime import date
from decimal import Decimal

from app.modules.quant_research.interfaces import (
    MarketRegime,
    RegimeAnalysis,
    RegimeConfig,
    RegimeIndicator,
    RegimeType,
)

ZERO = Decimal(0)
ONE = Decimal(1)


class RegimeDetector:
    """Detects market regimes using statistical methods."""

    def __init__(self, config: RegimeConfig | None = None) -> None:
        self._config = config or RegimeConfig()

    def detect_regime(
        self,
        prices: list[tuple[date, Decimal]],
        volumes: list[tuple[date, Decimal]] | None = None,
    ) -> RegimeAnalysis:
        """Detect current regime using rolling statistics method."""
        sorted_prices = sorted(prices, key=lambda p: p[0])
        if len(sorted_prices) < self._config.lookback_days:
            return RegimeAnalysis(
                current_regime=RegimeType.NORMAL,
                confidence=ZERO,
                regime_history=[],
                indicators=[],
                transition_probabilities={},
            )

        price_values = [p[1] for p in sorted_prices]
        returns = [
            (price_values[i] - price_values[i - 1]) / price_values[i - 1]
            if price_values[i - 1] != ZERO
            else ZERO
            for i in range(1, len(price_values))
        ]

        volatility = self._compute_rolling_volatility(returns, self._config.vol_window)
        trend = self._compute_trend(price_values, self._config.trend_window)
        drawdown = self._compute_drawdown(price_values)

        regime_type, confidence = self._classify_regime(volatility, trend, drawdown)

        # Build indicators
        indicators = [
            RegimeIndicator(
                name="volatility",
                value=volatility,
                threshold_low=self._config.vol_threshold_low,
                threshold_high=self._config.vol_threshold_high,
                signal="bearish"
                if volatility > self._config.vol_threshold_high
                else ("bullish" if volatility < self._config.vol_threshold_low else "neutral"),
            ),
            RegimeIndicator(
                name="trend",
                value=trend,
                threshold_low=Decimal("-0.05"),
                threshold_high=Decimal("0.05"),
                signal="bullish"
                if trend > Decimal("0.05")
                else ("bearish" if trend < Decimal("-0.05") else "neutral"),
            ),
            RegimeIndicator(
                name="drawdown",
                value=drawdown,
                threshold_low=Decimal("-0.10"),
                threshold_high=ZERO,
                signal="bearish" if drawdown < Decimal("-0.10") else "neutral",
            ),
        ]

        # Build regime history from the data
        regime_history = self._build_regime_history(sorted_prices, returns)
        transition_probs = self._build_transition_matrix(regime_history)

        return RegimeAnalysis(
            current_regime=regime_type,
            confidence=confidence,
            regime_history=regime_history,
            indicators=indicators,
            transition_probabilities=transition_probs,
        )

    def _classify_regime(
        self, volatility: Decimal, trend: Decimal, drawdown: Decimal
    ) -> tuple[RegimeType, Decimal]:
        """Classify regime from indicators. Returns (regime, confidence)."""
        high = self._config.vol_threshold_high
        low = self._config.vol_threshold_low

        # CRISIS: drawdown > 20% AND vol > high_threshold
        if drawdown < Decimal("-0.20") and volatility > high:
            confidence = min(ONE, abs(drawdown) + volatility)
            return RegimeType.CRISIS, confidence

        # BEAR: trend < 0 AND vol > low_threshold
        if trend < ZERO and volatility > low:
            confidence = min(ONE, abs(trend) + (volatility - low))
            return RegimeType.BEAR, confidence

        # HIGH_VOL: vol > high_threshold AND trend >= 0
        if volatility > high and trend >= ZERO:
            confidence = min(ONE, (volatility - high) * Decimal(5) + Decimal("0.5"))
            return RegimeType.HIGH_VOL, confidence

        # RECOVERY: trend > 0 AND recent drawdown was > 10%
        if trend > ZERO and drawdown < Decimal("-0.10"):
            confidence = min(ONE, trend + abs(drawdown))
            return RegimeType.RECOVERY, confidence

        # BULL: trend > 0 AND vol < low_threshold
        if trend > ZERO and volatility < low:
            confidence = min(ONE, trend * Decimal(5) + Decimal("0.5"))
            return RegimeType.BULL, confidence

        # LOW_VOL: vol < low_threshold * 0.7
        if volatility < low * Decimal("0.7"):
            confidence = min(
                ONE, (low * Decimal("0.7") - volatility) * Decimal(10) + Decimal("0.5")
            )
            return RegimeType.LOW_VOL, confidence

        # NORMAL: everything else
        return RegimeType.NORMAL, Decimal("0.5")

    def _compute_rolling_volatility(self, returns: list[Decimal], window: int) -> Decimal:
        """Annualized rolling volatility over the given window."""
        if len(returns) < window:
            return ZERO
        recent = returns[-window:]
        if len(recent) < 2:
            return ZERO
        std = Decimal(str(statistics.stdev(float(r) for r in recent)))
        # Annualize (sqrt(252))
        return std * Decimal("15.8745")  # sqrt(252) ~ 15.8745

    def _compute_trend(self, prices: list[Decimal], window: int) -> Decimal:
        """Return over the trend window as a fraction."""
        if len(prices) < window:
            return ZERO
        start = prices[-window]
        end = prices[-1]
        if start == ZERO:
            return ZERO
        return (end - start) / start

    def _compute_drawdown(self, prices: list[Decimal]) -> Decimal:
        """Current drawdown from peak."""
        if not prices:
            return ZERO
        peak = max(prices)
        if peak == ZERO:
            return ZERO
        return (prices[-1] - peak) / peak

    def _build_regime_history(
        self,
        sorted_prices: list[tuple[date, Decimal]],
        returns: list[Decimal],
    ) -> list[MarketRegime]:
        """Build a simplified regime history by evaluating rolling windows."""
        if len(returns) < self._config.lookback_days:
            return []

        history: list[MarketRegime] = []
        step = self._config.vol_window
        price_values = [p[1] for p in sorted_prices]

        prev_regime: RegimeType | None = None
        prev_confidence: Decimal = Decimal("0.5")
        prev_indicators: dict = {}
        regime_start: date | None = None

        for i in range(self._config.lookback_days, len(returns), step):
            window_returns = returns[max(0, i - self._config.vol_window) : i]
            window_prices = price_values[: i + 1]
            trend_prices = price_values[max(0, i - self._config.trend_window) : i + 1]

            vol = self._compute_rolling_volatility(window_returns, len(window_returns))
            trend = self._compute_trend(trend_prices, len(trend_prices))
            dd = self._compute_drawdown(window_prices)

            regime_type, confidence = self._classify_regime(vol, trend, dd)
            current_date = sorted_prices[i][0]

            if regime_type != prev_regime:
                if prev_regime is not None and regime_start is not None:
                    history.append(
                        MarketRegime(
                            regime_type=prev_regime,
                            start_date=regime_start,
                            end_date=current_date,
                            confidence=prev_confidence,
                            indicators=prev_indicators,
                        )
                    )
                prev_regime = regime_type
                regime_start = current_date
            prev_confidence = confidence
            prev_indicators = {"volatility": vol, "trend": trend, "drawdown": dd}

        # Append final regime (open-ended)
        if prev_regime is not None and regime_start is not None:
            history.append(
                MarketRegime(
                    regime_type=prev_regime,
                    start_date=regime_start,
                    end_date=None,
                    confidence=prev_confidence,
                    indicators=prev_indicators,
                )
            )

        return history

    def _build_transition_matrix(
        self, regime_history: list[MarketRegime]
    ) -> dict[str, dict[str, float]]:
        """Build regime transition probability matrix from history."""
        if len(regime_history) < 2:
            return {}

        transitions: dict[str, dict[str, int]] = {}
        for i in range(len(regime_history) - 1):
            from_r = regime_history[i].regime_type.value
            to_r = regime_history[i + 1].regime_type.value
            if from_r not in transitions:
                transitions[from_r] = {}
            transitions[from_r][to_r] = transitions[from_r].get(to_r, 0) + 1

        # Normalize to probabilities
        matrix: dict[str, dict[str, float]] = {}
        for from_r, targets in transitions.items():
            total = sum(targets.values())
            if total > 0:
                matrix[from_r] = {to_r: round(count / total, 4) for to_r, count in targets.items()}
            else:
                matrix[from_r] = {to_r: 0.0 for to_r in targets}
        return matrix
