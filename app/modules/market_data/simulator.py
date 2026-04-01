"""Market data simulator using Geometric Brownian Motion.

Generates realistic correlated price movements for local development.
Uses Cholesky decomposition for inter-instrument correlation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import structlog

from app.shared.events import BaseEvent, EventBus

logger = structlog.get_logger()


@dataclass
class InstrumentConfig:
    ticker: str
    initial_price: float
    annual_drift: float  # mu — expected return
    annual_volatility: float  # sigma — annualized vol
    spread_bps: float = 10.0  # bid-ask spread in basis points


# Sector-correlated instrument universe
DEFAULT_UNIVERSE: list[InstrumentConfig] = [
    # Technology (high vol, high drift, correlated)
    InstrumentConfig("AAPL", 190.0, 0.12, 0.25, 8.0),
    InstrumentConfig("MSFT", 420.0, 0.10, 0.22, 6.0),
    InstrumentConfig("GOOGL", 175.0, 0.08, 0.28, 10.0),
    InstrumentConfig("NVDA", 880.0, 0.15, 0.45, 15.0),
    # Consumer Discretionary
    InstrumentConfig("AMZN", 185.0, 0.10, 0.30, 10.0),
    InstrumentConfig("TSLA", 175.0, 0.05, 0.55, 25.0),
    # Financials (lower vol)
    InstrumentConfig("JPM", 200.0, 0.08, 0.20, 6.0),
    InstrumentConfig("GS", 470.0, 0.07, 0.22, 8.0),
    # Healthcare (defensive)
    InstrumentConfig("JNJ", 155.0, 0.05, 0.15, 5.0),
    # Energy
    InstrumentConfig("XOM", 115.0, 0.06, 0.25, 8.0),
]

# Block-diagonal correlation matrix by sector
# Tech: 0.7 intra, Consumer: 0.5, Financials: 0.6, cross-sector: 0.2
SECTOR_GROUPS = [[0, 1, 2, 3], [4, 5], [6, 7], [8], [9]]
INTRA_SECTOR_CORR = 0.6
CROSS_SECTOR_CORR = 0.2


def _build_correlation_matrix(n: int) -> np.ndarray[np.floating]:  # type: ignore[type-var]
    """Build block-diagonal correlation matrix from sector groups."""
    corr = np.full((n, n), CROSS_SECTOR_CORR)
    np.fill_diagonal(corr, 1.0)
    for group in SECTOR_GROUPS:
        for i in group:
            for j in group:
                if i != j and i < n and j < n:
                    corr[i, j] = INTRA_SECTOR_CORR
    return corr


@dataclass
class MarketDataSimulator:
    """Generates correlated price ticks via GBM and publishes to event bus."""

    event_bus: EventBus
    universe: list[InstrumentConfig] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    interval_ms: int = 1000
    _prices: dict[str, float] = field(default_factory=dict, init=False)
    _cholesky: np.ndarray | None = field(default=None, init=False)  # type: ignore[type-arg]
    _running: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        # Initialize current prices
        for cfg in self.universe:
            self._prices[cfg.ticker] = cfg.initial_price
        # Precompute Cholesky decomposition of correlation matrix
        n = len(self.universe)
        corr = _build_correlation_matrix(n)
        self._cholesky = np.linalg.cholesky(corr)

    def _generate_tick(self) -> dict[str, float]:
        """Generate one set of correlated price changes using GBM."""
        n = len(self.universe)
        dt = self.interval_ms / (252 * 6.5 * 3600 * 1000)  # fraction of trading year

        # Independent normals → correlated via Cholesky
        z = np.random.standard_normal(n)
        correlated_z = self._cholesky @ z  # type: ignore[union-attr]

        new_prices: dict[str, float] = {}
        for i, cfg in enumerate(self.universe):
            s = self._prices[cfg.ticker]
            # GBM: dS = mu*S*dt + sigma*S*dW
            drift = cfg.annual_drift * s * dt
            diffusion = cfg.annual_volatility * s * np.sqrt(dt) * correlated_z[i]
            ds = drift + diffusion
            new_price = max(s + ds, 0.01)  # floor at 1 cent
            self._prices[cfg.ticker] = new_price
            new_prices[cfg.ticker] = new_price

        return new_prices

    async def _publish_prices(self, prices: dict[str, float]) -> None:
        """Publish price snapshots to the event bus."""
        now = datetime.now(UTC)
        for cfg in self.universe:
            price = prices[cfg.ticker]
            spread = price * cfg.spread_bps / 10_000
            half_spread = spread / 2
            mid = round(price, 4)
            bid = round(price - half_spread, 4)
            ask = round(price + half_spread, 4)

            event = BaseEvent(
                event_type="price.updated",
                data={
                    "instrument_id": cfg.ticker,
                    "bid": str(bid),
                    "ask": str(ask),
                    "mid": str(mid),
                    "timestamp": now.isoformat(),
                    "source": "simulator",
                },
            )
            await self.event_bus.publish("prices.normalized", event)

    async def run(self) -> None:
        """Main loop — generate and publish prices at configured interval."""
        self._running = True
        logger.info(
            "simulator_started",
            instruments=len(self.universe),
            interval_ms=self.interval_ms,
        )
        while self._running:
            prices = self._generate_tick()
            await self._publish_prices(prices)
            await asyncio.sleep(self.interval_ms / 1000)

    def stop(self) -> None:
        self._running = False
        logger.info("simulator_stopped")
