"""Intraday volume profile — U-shaped curve matching real equity market patterns.

Used by the ambient flow generator to distribute daily volume across
the trading session, and by VWAP benchmarks for weighting.

The profile is parameterized per exchange trading hours:
- US (NYSE/NASDAQ): 390 minutes (09:30-16:00 ET)
- LSE: 510 minutes (08:00-16:30 GMT)
- Default: 390 minutes
"""

from __future__ import annotations

import math


class IntradayVolumeProfile:
    """Generates the fraction of ADV expected at each minute of the trading day.

    Uses a U-shaped ("smile") profile:
    - High volume at open (~15% in first 30 min)
    - Low volume midday
    - High volume at close (~30% in last 60 min)
    """

    def __init__(self, trading_minutes: int = 390) -> None:
        self._trading_minutes = trading_minutes
        self._weights = self._build_weights()
        self._cumulative = self._build_cumulative()

    def _build_weights(self) -> list[float]:
        """Build per-minute volume weights using a bathtub curve."""
        n = self._trading_minutes
        weights: list[float] = []
        for m in range(n):
            t = m / max(n - 1, 1)
            # Bathtub: high at edges (t=0, t=1), low in middle (t=0.5)
            # Using polynomial: w(t) = a*(2t-1)^4 + b
            x = 2.0 * t - 1.0
            w = 2.0 * x**4 + 0.3
            weights.append(w)

        # Normalize so they sum to 1.0
        total = sum(weights)
        return [w / total for w in weights]

    def _build_cumulative(self) -> list[float]:
        """Precompute cumulative fractions."""
        cum: list[float] = []
        running = 0.0
        for w in self._weights:
            running += w
            cum.append(running)
        return cum

    @property
    def trading_minutes(self) -> int:
        return self._trading_minutes

    def fraction_at_minute(self, minute: int) -> float:
        """Return fraction of ADV expected at this minute of the day."""
        if minute < 0 or minute >= self._trading_minutes:
            return 0.0
        return self._weights[minute]

    def cumulative_fraction(self, minute: int) -> float:
        """Return cumulative fraction of ADV expected by this minute."""
        if minute < 0:
            return 0.0
        if minute >= self._trading_minutes:
            return 1.0
        return self._cumulative[minute]

    def volume_at_minute(self, minute: int, adv: int) -> int:
        """Return expected volume (shares) at this minute given an ADV."""
        return max(1, int(math.ceil(self.fraction_at_minute(minute) * adv)))


# Pre-built profiles for common exchanges
US_PROFILE = IntradayVolumeProfile(trading_minutes=390)
LSE_PROFILE = IntradayVolumeProfile(trading_minutes=510)
DEFAULT_PROFILE = US_PROFILE
