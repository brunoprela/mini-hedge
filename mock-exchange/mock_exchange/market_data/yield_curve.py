"""Yield curve simulation — per-currency term structures with mean reversion.

Provides realistic interest rate term structures for:
- FX forward pricing (covered interest rate parity)
- Future fixed income modeling (bond pricing, duration, convexity)

Each currency has a base curve defined by pillar rates at standard tenors.
Rates evolve via an Ornstein-Uhlenbeck (mean-reverting) process with
correlated parallel + slope + curvature shocks.

Interpolation uses linear-on-log-tenor for simplicity — sufficient for
FX forward pricing and basic bond analytics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import structlog

logger = structlog.get_logger()

# Standard tenors in days
PILLAR_TENORS = [1, 7, 30, 90, 180, 360, 720, 1800, 3600]
PILLAR_LABELS = ["ON", "1W", "1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y"]


@dataclass(frozen=True)
class CurvePoint:
    """A single point on the yield curve."""

    tenor_days: int
    tenor_label: str
    rate: float  # annualized continuously compounded rate


@dataclass(frozen=True)
class YieldCurveSnapshot:
    """Full yield curve at a point in time."""

    currency: str
    points: list[CurvePoint]
    timestamp: datetime

    def rate_at_tenor(self, tenor_days: int) -> float:
        """Interpolate rate for arbitrary tenor via linear-on-log-tenor."""
        if tenor_days <= 0:
            return self.points[0].rate

        tenors = [p.tenor_days for p in self.points]
        rates = [p.rate for p in self.points]

        # Clamp to curve boundaries
        if tenor_days <= tenors[0]:
            return rates[0]
        if tenor_days >= tenors[-1]:
            return rates[-1]

        # Linear interpolation on log(tenor)
        log_target = math.log(tenor_days)
        for i in range(len(tenors) - 1):
            if tenors[i] <= tenor_days <= tenors[i + 1]:
                log_lo = math.log(tenors[i])
                log_hi = math.log(tenors[i + 1])
                frac = (log_target - log_lo) / (log_hi - log_lo)
                return rates[i] + frac * (rates[i + 1] - rates[i])

        return rates[-1]  # fallback

    def discount_factor(self, tenor_days: int) -> float:
        """Compute discount factor: exp(-r * T)."""
        rate = self.rate_at_tenor(tenor_days)
        t = tenor_days / 360.0
        return math.exp(-rate * t)

    def forward_rate(self, start_days: int, end_days: int) -> float:
        """Implied forward rate between two tenors."""
        if end_days <= start_days:
            return self.rate_at_tenor(start_days)
        df_start = self.discount_factor(start_days)
        df_end = self.discount_factor(end_days)
        t = (end_days - start_days) / 360.0
        if t <= 0 or df_end <= 0:
            return 0.0
        return -math.log(df_end / df_start) / t


@dataclass
class CurrencyCurveConfig:
    """Initial yield curve configuration for a currency."""

    currency: str
    # Pillar rates (annualized) — must match PILLAR_TENORS length
    pillar_rates: list[float]
    # OU mean reversion speed (higher = faster reversion)
    mean_reversion: float = 5.0
    # OU volatility (annualized, in rate terms e.g. 0.005 = 50bps/year)
    volatility: float = 0.005


# Realistic base curves for major currencies (as of ~2024-2025 regime)
DEFAULT_CURVES: list[CurrencyCurveConfig] = [
    # USD — Fed funds ~5.25%, inverted short end, normal long end
    CurrencyCurveConfig(
        "USD",
        #  ON     1W     1M     3M     6M     1Y     2Y     5Y     10Y
        [0.0530, 0.0528, 0.0525, 0.0510, 0.0490, 0.0460, 0.0430, 0.0410, 0.0420],
    ),
    # EUR — ECB deposit ~3.75%, relatively flat
    CurrencyCurveConfig(
        "EUR",
        [0.0375, 0.0373, 0.0370, 0.0360, 0.0345, 0.0325, 0.0305, 0.0290, 0.0300],
    ),
    # GBP — BoE ~5.25%, similar shape to USD
    CurrencyCurveConfig(
        "GBP",
        [0.0525, 0.0523, 0.0520, 0.0505, 0.0485, 0.0455, 0.0425, 0.0405, 0.0415],
    ),
    # JPY — BoJ ~0.10%, near zero with slight upslope
    CurrencyCurveConfig(
        "JPY",
        [0.0010, 0.0010, 0.0010, 0.0012, 0.0015, 0.0025, 0.0040, 0.0060, 0.0085],
    ),
    # CHF — SNB ~1.75%, flat-ish
    CurrencyCurveConfig(
        "CHF",
        [0.0175, 0.0174, 0.0172, 0.0168, 0.0162, 0.0150, 0.0140, 0.0135, 0.0140],
    ),
    # AUD — RBA ~4.35%
    CurrencyCurveConfig(
        "AUD",
        [0.0435, 0.0433, 0.0430, 0.0420, 0.0405, 0.0385, 0.0365, 0.0355, 0.0370],
    ),
    # CAD — BoC ~5.00%
    CurrencyCurveConfig(
        "CAD",
        [0.0500, 0.0498, 0.0495, 0.0480, 0.0460, 0.0435, 0.0410, 0.0395, 0.0405],
    ),
    # DKK — pegged to EUR, slight premium
    CurrencyCurveConfig(
        "DKK",
        [0.0380, 0.0378, 0.0375, 0.0365, 0.0350, 0.0330, 0.0310, 0.0295, 0.0305],
    ),
    # KRW — BoK ~3.50%
    CurrencyCurveConfig(
        "KRW",
        [0.0350, 0.0348, 0.0345, 0.0340, 0.0335, 0.0325, 0.0315, 0.0310, 0.0320],
    ),
    # TWD — CBC ~1.875%
    CurrencyCurveConfig(
        "TWD",
        [0.0188, 0.0187, 0.0185, 0.0182, 0.0178, 0.0172, 0.0165, 0.0160, 0.0165],
    ),
    # HKD — HKMA linked to USD
    CurrencyCurveConfig(
        "HKD",
        [0.0535, 0.0533, 0.0530, 0.0515, 0.0495, 0.0465, 0.0435, 0.0415, 0.0425],
    ),
    # BRL — BCB ~10.50%, steep curve
    CurrencyCurveConfig(
        "BRL",
        [0.1050, 0.1048, 0.1040, 0.1020, 0.1000, 0.0980, 0.0960, 0.0950, 0.0970],
        volatility=0.010,  # EM rates are more volatile
    ),
]


@dataclass
class YieldCurveSimulator:
    """Simulates yield curve evolution via Ornstein-Uhlenbeck process.

    Each pillar rate evolves independently with mean reversion to its
    initial level. Parallel (level), slope, and curvature shocks provide
    cross-pillar correlation.

    Call ``tick()`` each simulation interval to evolve rates.
    """

    configs: list[CurrencyCurveConfig] = field(
        default_factory=lambda: list(DEFAULT_CURVES),
    )
    interval_ms: int = 1000

    # Current pillar rates per currency: {"USD": [0.053, 0.0528, ...]}
    _rates: dict[str, list[float]] = field(default_factory=dict, init=False)
    # Long-run mean (initial rates)
    _means: dict[str, list[float]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for cfg in self.configs:
            self._rates[cfg.currency] = list(cfg.pillar_rates)
            self._means[cfg.currency] = list(cfg.pillar_rates)

    def tick(self) -> dict[str, YieldCurveSnapshot]:
        """Advance all curves by one interval. Returns current snapshots."""
        dt = self.interval_ms / (252 * 6.5 * 3600 * 1000)  # same as GBM
        now = datetime.now(UTC)
        snapshots: dict[str, YieldCurveSnapshot] = {}

        for cfg in self.configs:
            rates = self._rates[cfg.currency]
            means = self._means[cfg.currency]
            n = len(rates)

            # Generate correlated shocks: parallel + slope + curvature
            z = np.random.standard_normal(3)
            parallel = z[0]  # shifts all rates equally
            slope = z[1]  # steepens/flattens (short end vs long end)
            curvature = z[2]  # belly effect

            for i in range(n):
                # Pillar weight for slope: -1 at short end, +1 at long end
                w_slope = 2.0 * i / max(n - 1, 1) - 1.0
                # Curvature: peaks at belly (i ≈ n/2)
                w_curve = 1.0 - abs(2.0 * i / max(n - 1, 1) - 1.0)

                shock = (
                    cfg.volatility
                    * math.sqrt(dt)
                    * (0.6 * parallel + 0.3 * slope * w_slope + 0.1 * curvature * w_curve)
                )

                # OU mean reversion: dr = kappa * (mu - r) * dt + sigma * dW
                drift = cfg.mean_reversion * (means[i] - rates[i]) * dt
                rates[i] = max(rates[i] + drift + shock, -0.01)  # allow slightly negative

            points = [
                CurvePoint(
                    tenor_days=PILLAR_TENORS[i],
                    tenor_label=PILLAR_LABELS[i],
                    rate=rates[i],
                )
                for i in range(n)
            ]
            snapshots[cfg.currency] = YieldCurveSnapshot(
                currency=cfg.currency, points=points, timestamp=now,
            )

        return snapshots

    def get_snapshot(self, currency: str) -> YieldCurveSnapshot | None:
        """Get current curve for a currency without advancing time."""
        rates = self._rates.get(currency)
        if rates is None:
            return None
        return YieldCurveSnapshot(
            currency=currency,
            points=[
                CurvePoint(
                    tenor_days=PILLAR_TENORS[i],
                    tenor_label=PILLAR_LABELS[i],
                    rate=rates[i],
                )
                for i in range(len(rates))
            ],
            timestamp=datetime.now(UTC),
        )

    def get_all_snapshots(self) -> dict[str, YieldCurveSnapshot]:
        """Get current curves for all currencies."""
        return {
            cfg.currency: self.get_snapshot(cfg.currency)  # type: ignore[misc]
            for cfg in self.configs
        }

    def get_rate(self, currency: str, tenor_days: int) -> float | None:
        """Get interpolated rate for a specific currency and tenor."""
        snapshot = self.get_snapshot(currency)
        if snapshot is None:
            return None
        return snapshot.rate_at_tenor(tenor_days)

    def get_discount_factor(self, currency: str, tenor_days: int) -> float | None:
        """Get discount factor for a specific currency and tenor."""
        snapshot = self.get_snapshot(currency)
        if snapshot is None:
            return None
        return snapshot.discount_factor(tenor_days)

    @property
    def currencies(self) -> list[str]:
        return [cfg.currency for cfg in self.configs]

    def rate_decimal(self, currency: str, tenor_days: int) -> Decimal | None:
        """Get rate as Decimal for API responses."""
        rate = self.get_rate(currency, tenor_days)
        if rate is None:
            return None
        return Decimal(str(round(rate, 6)))
