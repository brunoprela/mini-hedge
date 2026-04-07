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
    from mock_exchange.market_data.order_book import SimulatedOrderBook
    from mock_exchange.market_data.trade_tape import TradeTape
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

@dataclass
class FXPairConfig:
    """FX pair configuration — rates expressed as 1 USD = X quote currency."""

    base: str  # always "USD"
    quote: str  # "GBP", "EUR", etc.
    initial_rate: float  # 1 USD = X quote
    annual_volatility: float  # FX vol (typically 5-12%)


# FX universe — covers all non-USD currencies in the equity universe.
# Rates are USD-based: 1 USD = X units of quote currency.
FX_UNIVERSE: list[FXPairConfig] = [
    FXPairConfig("USD", "GBP", 0.79, 0.08),   # British Pound
    FXPairConfig("USD", "EUR", 0.92, 0.08),   # Euro
    FXPairConfig("USD", "JPY", 154.5, 0.10),  # Japanese Yen
    FXPairConfig("USD", "CHF", 0.88, 0.09),   # Swiss Franc
    FXPairConfig("USD", "DKK", 6.88, 0.08),   # Danish Krone (pegged to EUR)
    FXPairConfig("USD", "KRW", 1380.0, 0.10), # South Korean Won
    FXPairConfig("USD", "TWD", 32.5, 0.06),   # Taiwan Dollar
    FXPairConfig("USD", "HKD", 7.81, 0.005),  # Hong Kong Dollar (pegged)
    FXPairConfig("USD", "AUD", 1.55, 0.10),   # Australian Dollar
    FXPairConfig("USD", "CAD", 1.37, 0.07),   # Canadian Dollar
    FXPairConfig("USD", "BRL", 5.05, 0.15),   # Brazilian Real
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
    fx_universe: list[FXPairConfig] = field(default_factory=lambda: list(FX_UNIVERSE))
    interval_ms: int = 1000
    order_books: dict[str, SimulatedOrderBook] = field(default_factory=dict)
    trade_tape: TradeTape | None = None
    _prices: dict[str, float] = field(default_factory=dict, init=False)
    _fx_rates: dict[str, float] = field(default_factory=dict, init=False)
    _cholesky: np.ndarray | None = field(default=None, init=False)  # type: ignore[type-arg]
    _running: bool = field(default=False, init=False)

    # Regime multipliers — adjusted by scenario engine
    drift_multiplier: float = 1.0
    volatility_multiplier: float = 1.0
    correlation_boost: float = 0.0

    def __post_init__(self) -> None:
        for cfg in self.universe:
            self._prices[cfg.ticker] = cfg.initial_price
        for fx in self.fx_universe:
            self._fx_rates[f"FX:{fx.base}/{fx.quote}"] = fx.initial_rate
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

    def _generate_fx_tick(self) -> dict[str, float]:
        """Generate FX rate ticks via independent GBM (zero drift)."""
        dt = self.interval_ms / (252 * 6.5 * 3600 * 1000)
        new_rates: dict[str, float] = {}
        for fx in self.fx_universe:
            pair_id = f"FX:{fx.base}/{fx.quote}"
            rate = self._fx_rates[pair_id]
            vol = fx.annual_volatility * self.volatility_multiplier
            z = np.random.standard_normal()
            new_rate = rate * (1 + vol * np.sqrt(dt) * z)
            new_rate = max(new_rate, 0.0001)
            self._fx_rates[pair_id] = new_rate
            new_rates[pair_id] = new_rate
        return new_rates

    def _publish_prices(self, prices: dict[str, float]) -> None:
        now = datetime.now(UTC)
        _q = Decimal("0.0001")
        for cfg in self.universe:
            price = prices[cfg.ticker]
            mid = Decimal(str(price)).quantize(_q, rounding=ROUND_HALF_UP)

            # Update order book mid and derive bid/ask from book
            book = self.order_books.get(cfg.ticker)
            if book:
                book.update_mid(mid)
                bb = book.best_bid
                ba = book.best_ask
                bid = bb.quantize(_q) if bb else mid
                ask = ba.quantize(_q) if ba else mid
            else:
                spread = price * cfg.spread_bps / 10_000
                half_spread = spread / 2
                bid = Decimal(str(price - half_spread)).quantize(_q, rounding=ROUND_HALF_UP)
                ask = Decimal(str(price + half_spread)).quantize(_q, rounding=ROUND_HALF_UP)

            # Volume from trade tape (real data) instead of random
            volume = 0
            if self.trade_tape:
                volume = self.trade_tape.daily_volume(cfg.ticker)
            if volume == 0:
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

        # Publish FX rates on the same topic
        fx_rates = self._generate_fx_tick()
        _q6 = Decimal("0.000001")
        for pair_id, rate in fx_rates.items():
            mid = Decimal(str(rate)).quantize(_q6, rounding=ROUND_HALF_UP)
            self.producer.produce(
                topic=PRICES_TOPIC,
                event_type="fx_rate.updated",
                data={
                    "instrument_id": pair_id,
                    "bid": str(mid),
                    "ask": str(mid),
                    "mid": str(mid),
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
