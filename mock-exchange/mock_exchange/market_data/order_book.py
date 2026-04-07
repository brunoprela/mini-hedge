"""Simulated order book — statistical model with spread, depth, and fill mechanics.

Not a real matching engine. Maintains a price ladder with synthetic liquidity
at each level. Real and ambient orders consume/add liquidity. The book is
re-centered around the GBM mid price on every simulator tick.

Key behaviors:
- Depth at each level is proportional to ADV / trading_minutes
- Spread widens during high-volatility regimes
- Market orders walk through levels, consuming liquidity and generating ticks
- Limit orders that cross the spread fill immediately; the rest adds resting liquidity
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from mock_exchange.shared.models import OrderBookLevel, OrderBookSnapshot, TradeTick


class SimulatedOrderBook:
    """Per-instrument order book with simulated depth."""

    def __init__(
        self,
        instrument_id: str,
        tick_size: float = 0.01,
        spread_bps: float = 10.0,
        avg_daily_volume: int = 10_000_000,
        trading_minutes: int = 390,
    ) -> None:
        self.instrument_id = instrument_id
        self._tick_size = Decimal(str(tick_size))
        self._base_spread_bps = spread_bps
        self._spread_multiplier = 1.0  # Adjusted by scenario engine
        self._adv = avg_daily_volume
        self._trading_minutes = trading_minutes

        # Typical per-level depth: fraction of per-minute volume
        self._base_depth = max(1, avg_daily_volume // (trading_minutes * 5))

        # Price ladder: {price: quantity}
        self._bids: dict[Decimal, int] = {}
        self._asks: dict[Decimal, int] = {}
        self._mid: Decimal = Decimal("100.0")

    @property
    def mid(self) -> Decimal:
        return self._mid

    @property
    def best_bid(self) -> Decimal | None:
        return max(self._bids.keys()) if self._bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return min(self._asks.keys()) if self._asks else None

    @property
    def spread_bps(self) -> float:
        bb = self.best_bid
        ba = self.best_ask
        if bb is None or ba is None or self._mid == 0:
            return self._base_spread_bps * self._spread_multiplier
        return float((ba - bb) / self._mid * 10000)

    def set_spread_multiplier(self, multiplier: float) -> None:
        """Adjust spread width — called by scenario engine for volatile regimes."""
        self._spread_multiplier = max(0.5, multiplier)

    def update_mid(self, new_mid: Decimal) -> None:
        """GBM tick arrived — recenter the book around the new mid price."""
        self._mid = new_mid
        spread = self._calculate_spread()
        half_spread = spread / 2

        new_best_bid = self._round_price(new_mid - half_spread)
        new_best_ask = self._round_price(new_mid + half_spread)

        # Remove stale levels outside the new spread window
        depth_range = self._tick_size * 20  # Keep 20 ticks of depth
        self._bids = {
            p: q for p, q in self._bids.items()
            if p <= new_best_bid and p >= new_best_bid - depth_range
        }
        self._asks = {
            p: q for p, q in self._asks.items()
            if p >= new_best_ask and p <= new_best_ask + depth_range
        }

        # Ensure there's always at least some liquidity at best bid/ask
        if new_best_bid not in self._bids:
            self._bids[new_best_bid] = self._base_depth
        if new_best_ask not in self._asks:
            self._asks[new_best_ask] = self._base_depth

    def add_liquidity(self, side: str, price: Decimal, quantity: int) -> None:
        """Add resting liquidity to the book (from ambient flow or limit orders)."""
        price = self._round_price(price)
        book = self._bids if side == "buy" else self._asks
        book[price] = book.get(price, 0) + quantity

    def execute_market_order(
        self, side: str, quantity: int, *, timestamp: datetime | None = None,
    ) -> list[TradeTick]:
        """Walk the book and fill a market order. Returns trade ticks."""
        if timestamp is None:
            timestamp = datetime.now(UTC)

        ticks: list[TradeTick] = []
        remaining = quantity
        # Buy order consumes asks; sell order consumes bids
        book = self._asks if side == "buy" else self._bids
        price_sort = sorted(book.keys()) if side == "buy" else sorted(book.keys(), reverse=True)

        for price in price_sort:
            if remaining <= 0:
                break
            available = book[price]
            fill_qty = min(remaining, available)

            ticks.append(TradeTick(
                instrument_id=self.instrument_id,
                price=price,
                quantity=fill_qty,
                side=side,
                timestamp=timestamp,
                is_ambient=False,
                aggressor="buyer" if side == "buy" else "seller",
            ))

            book[price] -= fill_qty
            if book[price] <= 0:
                del book[price]
            remaining -= fill_qty

        return ticks

    def execute_limit_order(
        self, side: str, price: Decimal, quantity: int,
        *, timestamp: datetime | None = None,
    ) -> tuple[list[TradeTick], int]:
        """Execute a limit order. Returns (fills, resting_quantity).

        Fills whatever crosses the spread immediately; the remainder
        becomes resting liquidity on the book.
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)
        price = self._round_price(price)
        ticks: list[TradeTick] = []
        remaining = quantity

        if side == "buy":
            # Buy limit crosses if price >= best ask
            sorted_asks = sorted(self._asks.keys())
            for ask_price in sorted_asks:
                if remaining <= 0 or ask_price > price:
                    break
                available = self._asks[ask_price]
                fill_qty = min(remaining, available)
                ticks.append(TradeTick(
                    instrument_id=self.instrument_id,
                    price=ask_price,
                    quantity=fill_qty,
                    side=side,
                    timestamp=timestamp,
                    is_ambient=False,
                    aggressor="buyer",
                ))
                self._asks[ask_price] -= fill_qty
                if self._asks[ask_price] <= 0:
                    del self._asks[ask_price]
                remaining -= fill_qty
        else:
            # Sell limit crosses if price <= best bid
            sorted_bids = sorted(self._bids.keys(), reverse=True)
            for bid_price in sorted_bids:
                if remaining <= 0 or bid_price < price:
                    break
                available = self._bids[bid_price]
                fill_qty = min(remaining, available)
                ticks.append(TradeTick(
                    instrument_id=self.instrument_id,
                    price=bid_price,
                    quantity=fill_qty,
                    side=side,
                    timestamp=timestamp,
                    is_ambient=False,
                    aggressor="seller",
                ))
                self._bids[bid_price] -= fill_qty
                if self._bids[bid_price] <= 0:
                    del self._bids[bid_price]
                remaining -= fill_qty

        # Remaining quantity rests on the book
        if remaining > 0:
            self.add_liquidity(side, price, remaining)

        return ticks, remaining

    def snapshot(self, depth: int = 5) -> OrderBookSnapshot:
        """Return a snapshot of the top N levels on each side."""
        sorted_bids = sorted(self._bids.keys(), reverse=True)[:depth]
        sorted_asks = sorted(self._asks.keys())[:depth]
        return OrderBookSnapshot(
            instrument_id=self.instrument_id,
            bids=[OrderBookLevel(price=p, quantity=self._bids[p]) for p in sorted_bids],
            asks=[OrderBookLevel(price=p, quantity=self._asks[p]) for p in sorted_asks],
            timestamp=datetime.now(UTC),
        )

    def total_bid_depth(self) -> int:
        return sum(self._bids.values())

    def total_ask_depth(self) -> int:
        return sum(self._asks.values())

    def _calculate_spread(self) -> Decimal:
        raw = self._base_spread_bps * self._spread_multiplier
        spread_pct = Decimal(str(raw)) / Decimal("10000")
        return self._round_price(self._mid * spread_pct)

    def _round_price(self, price: Decimal) -> Decimal:
        quantized = (price / self._tick_size).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
        return quantized * self._tick_size
