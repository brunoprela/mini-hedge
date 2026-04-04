"""GBM price simulator — generates correlated multi-asset price movements.

Moved from app/modules/market_data/simulator.py to mock-exchange service.
Uses Cholesky decomposition for inter-instrument correlation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

import numpy as np
import structlog

if TYPE_CHECKING:
    from mock_exchange.shared.kafka import MockExchangeProducer

logger = structlog.get_logger()

PRICES_TOPIC = "shared.prices.normalized"


@dataclass
class InstrumentConfig:
    ticker: str
    initial_price: float
    annual_drift: float  # mu — expected return
    annual_volatility: float  # sigma — annualized vol
    spread_bps: float = 10.0  # bid-ask spread in basis points


# Sector-correlated instrument universe — global, multi-sector.
# Must stay in sync with reference_data/instruments.py (same tickers).
DEFAULT_UNIVERSE: list[InstrumentConfig] = [
    # US Technology (indices 0-4)
    InstrumentConfig("AAPL", 190.0, 0.12, 0.25, 8.0),     # 0
    InstrumentConfig("MSFT", 420.0, 0.10, 0.22, 6.0),     # 1
    InstrumentConfig("GOOGL", 175.0, 0.08, 0.28, 10.0),   # 2
    InstrumentConfig("NVDA", 880.0, 0.15, 0.45, 15.0),    # 3
    InstrumentConfig("META", 500.0, 0.11, 0.35, 12.0),    # 4
    # US Consumer Discretionary (5-7)
    InstrumentConfig("AMZN", 185.0, 0.10, 0.30, 10.0),    # 5
    InstrumentConfig("TSLA", 175.0, 0.05, 0.55, 25.0),    # 6
    InstrumentConfig("DIS", 110.0, 0.04, 0.30, 12.0),     # 7
    # US Financials (8-11)
    InstrumentConfig("JPM", 200.0, 0.08, 0.20, 6.0),      # 8
    InstrumentConfig("GS", 470.0, 0.07, 0.22, 8.0),       # 9
    InstrumentConfig("BRK.B", 410.0, 0.07, 0.15, 5.0),    # 10
    InstrumentConfig("V", 280.0, 0.09, 0.20, 6.0),        # 11
    # US Healthcare (12-14)
    InstrumentConfig("JNJ", 155.0, 0.05, 0.15, 5.0),      # 12
    InstrumentConfig("UNH", 525.0, 0.09, 0.20, 6.0),      # 13
    InstrumentConfig("PFE", 28.0, 0.03, 0.25, 10.0),      # 14
    # US Energy (15-16)
    InstrumentConfig("XOM", 115.0, 0.06, 0.25, 8.0),      # 15
    InstrumentConfig("CVX", 155.0, 0.06, 0.24, 8.0),      # 16
    # US Consumer Staples (17-18)
    InstrumentConfig("PG", 165.0, 0.04, 0.12, 5.0),       # 17
    InstrumentConfig("KO", 62.0, 0.03, 0.14, 5.0),        # 18
    # UK (19-23)
    InstrumentConfig("AZN", 120.0, 0.07, 0.20, 8.0),      # 19
    InstrumentConfig("HSBA", 7.50, 0.04, 0.18, 10.0),     # 20
    InstrumentConfig("SHEL", 28.0, 0.05, 0.22, 8.0),      # 21
    InstrumentConfig("ULVR", 42.0, 0.03, 0.15, 6.0),      # 22
    InstrumentConfig("RIO", 62.0, 0.05, 0.28, 10.0),      # 23
    InstrumentConfig("BP", 5.50, 0.04, 0.24, 10.0),       # 24
    # Germany (25-26)
    InstrumentConfig("SAP", 195.0, 0.10, 0.25, 8.0),      # 25
    InstrumentConfig("SIE", 180.0, 0.06, 0.22, 8.0),      # 26
    # France (27-28)
    InstrumentConfig("MC", 750.0, 0.08, 0.28, 10.0),      # 27
    InstrumentConfig("TTE", 58.0, 0.05, 0.22, 8.0),       # 28
    # Netherlands (29)
    InstrumentConfig("ASML", 950.0, 0.12, 0.35, 10.0),    # 29
    # Denmark (30)
    InstrumentConfig("NOVO.B", 130.0, 0.10, 0.28, 8.0),   # 30
    # Japan (31-32)
    InstrumentConfig("7203", 22.0, 0.04, 0.20, 10.0),     # 31
    InstrumentConfig("6758", 85.0, 0.06, 0.30, 12.0),     # 32
    # Switzerland (33-35)
    InstrumentConfig("NESN", 95.0, 0.03, 0.12, 5.0),      # 33
    InstrumentConfig("NOVN", 88.0, 0.05, 0.18, 6.0),      # 34
    InstrumentConfig("ROG", 245.0, 0.04, 0.16, 6.0),      # 35
    # South Korea (36)
    InstrumentConfig("005930", 55.0, 0.08, 0.30, 15.0),   # 36
    # Taiwan (37)
    InstrumentConfig("2330", 140.0, 0.10, 0.32, 12.0),    # 37
    # China/HK (38)
    InstrumentConfig("9988", 80.0, 0.06, 0.40, 18.0),     # 38
    # Australia (39)
    InstrumentConfig("BHP", 60.0, 0.06, 0.25, 10.0),      # 39
    # Canada (40)
    InstrumentConfig("RY", 110.0, 0.05, 0.16, 6.0),       # 40
    # Brazil (41)
    InstrumentConfig("VALE3", 14.0, 0.05, 0.35, 15.0),    # 41
]

SECTOR_GROUPS = [
    [0, 1, 2, 3, 4, 25, 29, 32, 36, 37, 38],  # Technology
    [5, 6, 7, 27, 31],                          # Consumer Discretionary
    [8, 9, 10, 11, 20, 40],                     # Financials
    [12, 13, 14, 19, 30, 34, 35],               # Healthcare
    [15, 16, 21, 24, 28],                        # Energy
    [17, 18, 22, 33],                            # Consumer Staples
    [26],                                         # Industrials
    [23, 39, 41],                                 # Materials
]
INTRA_SECTOR_CORR = 0.6
CROSS_SECTOR_CORR = 0.2


def _build_correlation_matrix(n: int) -> np.ndarray[np.floating]:  # type: ignore[type-var]
    corr = np.full((n, n), CROSS_SECTOR_CORR)
    np.fill_diagonal(corr, 1.0)
    for group in SECTOR_GROUPS:
        for i in group:
            for j in group:
                if i != j and i < n and j < n:
                    corr[i, j] = INTRA_SECTOR_CORR
    return corr


@dataclass
class GBMSimulator:
    """Generates correlated price ticks via GBM and publishes to Kafka."""

    producer: MockExchangeProducer
    universe: list[InstrumentConfig] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    interval_ms: int = 1000
    _prices: dict[str, float] = field(default_factory=dict, init=False)
    _cholesky: np.ndarray | None = field(default=None, init=False)  # type: ignore[type-arg]
    _running: bool = field(default=False, init=False)

    # Regime multipliers — adjusted by scenario engine
    drift_multiplier: float = 1.0
    volatility_multiplier: float = 1.0
    correlation_boost: float = 0.0

    def __post_init__(self) -> None:
        for cfg in self.universe:
            self._prices[cfg.ticker] = cfg.initial_price
        self._rebuild_cholesky()

    def _rebuild_cholesky(self) -> None:
        n = len(self.universe)
        corr = _build_correlation_matrix(n)
        if self.correlation_boost > 0:
            # Boost all off-diagonal correlations
            mask = ~np.eye(n, dtype=bool)
            corr[mask] = np.clip(corr[mask] + self.correlation_boost, -1.0, 0.99)
        self._cholesky = np.linalg.cholesky(corr)

    def apply_regime(
        self,
        drift_mult: float,
        vol_mult: float,
        corr_boost: float,
    ) -> None:
        """Apply market regime parameters from scenario engine."""
        self.drift_multiplier = drift_mult
        self.volatility_multiplier = vol_mult
        self.correlation_boost = corr_boost
        self._rebuild_cholesky()

    def reset_regime(self) -> None:
        self.drift_multiplier = 1.0
        self.volatility_multiplier = 1.0
        self.correlation_boost = 0.0
        self._rebuild_cholesky()

    @property
    def current_prices(self) -> dict[str, float]:
        return dict(self._prices)

    def _generate_tick(self) -> dict[str, float]:
        n = len(self.universe)
        dt = self.interval_ms / (252 * 6.5 * 3600 * 1000)

        z = np.random.standard_normal(n)
        correlated_z = self._cholesky @ z  # type: ignore[union-attr]

        new_prices: dict[str, float] = {}
        for i, cfg in enumerate(self.universe):
            s = self._prices[cfg.ticker]
            drift = (cfg.annual_drift * self.drift_multiplier) * s * dt
            vol = cfg.annual_volatility * self.volatility_multiplier
            diffusion = vol * s * np.sqrt(dt) * correlated_z[i]
            new_price = max(s + drift + diffusion, 0.01)
            self._prices[cfg.ticker] = new_price
            new_prices[cfg.ticker] = new_price
        return new_prices

    def _publish_prices(self, prices: dict[str, float]) -> None:
        now = datetime.now(UTC)
        _q = Decimal("0.0001")
        for cfg in self.universe:
            price = prices[cfg.ticker]
            spread = price * cfg.spread_bps / 10_000
            half_spread = spread / 2
            mid = Decimal(str(price)).quantize(_q, rounding=ROUND_HALF_UP)
            bid = Decimal(str(price - half_spread)).quantize(_q, rounding=ROUND_HALF_UP)
            ask = Decimal(str(price + half_spread)).quantize(_q, rounding=ROUND_HALF_UP)
            volume = int(np.random.exponential(scale=10_000 / max(price, 1)))

            self.producer.produce(
                topic=PRICES_TOPIC,
                event_type="price.updated",
                data={
                    "instrument_id": cfg.ticker,
                    "bid": str(bid),
                    "ask": str(ask),
                    "mid": str(mid),
                    "volume": str(volume),
                    "timestamp": now.isoformat(),
                    "source": "mock-exchange",
                },
            )
        self.producer.flush(timeout=0.5)

    async def run(self) -> None:
        self._running = True
        logger.info(
            "simulator_started",
            instruments=len(self.universe),
            interval_ms=self.interval_ms,
        )
        while self._running:
            prices = self._generate_tick()
            self._publish_prices(prices)
            await asyncio.sleep(self.interval_ms / 1000)

    def stop(self) -> None:
        self._running = False
        logger.info("simulator_stopped")
