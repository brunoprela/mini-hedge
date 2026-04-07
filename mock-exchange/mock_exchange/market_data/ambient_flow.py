"""Ambient flow generator — creates synthetic market activity.

Runs as an asyncio background task. Each tick:
1. For each instrument, determine target volume based on ADV and intraday profile
2. Generate limit orders near the spread to replenish book depth
3. Occasionally generate market orders that cross the spread (creating trades)
4. Record all trades on the trade tape

This produces ~80-90% of each instrument's daily volume as ambient noise,
leaving ~10-20% headroom for real platform orders.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from mock_exchange.execution.trading_hours import get_schedule

if TYPE_CHECKING:
    from mock_exchange.market_data.order_book import SimulatedOrderBook
    from mock_exchange.market_data.trade_tape import TradeTape
    from mock_exchange.market_data.volume_profile import IntradayVolumeProfile
    from mock_exchange.shared.models import InstrumentInfo

logger = structlog.get_logger()


class AmbientFlowGenerator:
    """Generates synthetic order flow to create realistic volume and book activity."""

    def __init__(
        self,
        order_books: dict[str, SimulatedOrderBook],
        instruments: dict[str, InstrumentInfo],
        volume_profile: IntradayVolumeProfile,
        trade_tape: TradeTape,
        interval_ms: int = 1000,
        ambient_fraction: float = 0.85,
    ) -> None:
        self._order_books = order_books
        self._instruments = instruments
        self._volume_profile = volume_profile
        self._trade_tape = trade_tape
        self._interval_s = interval_ms / 1000.0
        self._ambient_fraction = ambient_fraction
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # Simulation minute counter (advances each interval)
        self._sim_minute = 0

    async def start(self) -> None:
        """Start the ambient flow generator."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("ambient_flow_started", interval_ms=int(self._interval_s * 1000))

    async def stop(self) -> None:
        """Stop the ambient flow generator."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("ambient_flow_stopped")

    async def _run(self) -> None:
        """Main loop — generate ambient activity each interval."""
        while self._running:
            try:
                self._generate_all()
                self._sim_minute = (self._sim_minute + 1) % self._volume_profile.trading_minutes
                await asyncio.sleep(self._interval_s)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ambient_flow_error")
                await asyncio.sleep(self._interval_s)

    def _generate_all(self) -> None:
        """Generate ambient orders for all instruments."""
        now = datetime.now(UTC)
        minute_fraction = self._volume_profile.fraction_at_minute(self._sim_minute)

        for ticker, book in self._order_books.items():
            instrument = self._instruments.get(ticker)
            if instrument is None:
                continue
            self._generate_for_instrument(instrument, book, minute_fraction, now)

    def _generate_for_instrument(
        self,
        instrument: InstrumentInfo,
        book: SimulatedOrderBook,
        minute_fraction: float,
        now: datetime,
    ) -> None:
        """Generate ambient orders for one instrument."""
        # Only generate flow when the instrument's exchange is open
        schedule = get_schedule(instrument.exchange)
        if schedule is not None and not schedule.is_open(now):
            return

        # Target volume for this tick: ADV * fraction * ambient_share / intervals_per_minute
        intervals_per_minute = max(1, int(60.0 / self._interval_s))
        target_volume = int(
            instrument.avg_daily_volume
            * minute_fraction
            * self._ambient_fraction
            / intervals_per_minute
        )

        if target_volume <= 0:
            return

        mid = book.mid
        tick_size = Decimal(str(instrument.tick_size))

        # Split between resting limit orders (80%) and crossing market orders (20%)
        limit_volume = int(target_volume * 0.8)
        market_volume = target_volume - limit_volume

        # Add resting limit orders to replenish book depth
        self._add_resting_orders(book, mid, tick_size, limit_volume, now)

        # Generate crossing market orders that create trades
        if market_volume > 0:
            self._generate_market_trades(book, market_volume, now)

    def _add_resting_orders(
        self,
        book: SimulatedOrderBook,
        mid: Decimal,
        tick_size: Decimal,
        total_volume: int,
        now: datetime,
    ) -> None:
        """Add resting limit orders at various price levels to build depth."""
        if total_volume <= 0:
            return

        # Distribute across 5-10 price levels on each side
        num_levels = random.randint(5, 10)
        per_level = max(1, total_volume // (num_levels * 2))

        for i in range(1, num_levels + 1):
            offset = tick_size * i
            bid_price = mid - offset
            ask_price = mid + offset

            # Add some randomness to quantities
            bid_qty = max(1, int(per_level * random.uniform(0.5, 1.5)))
            ask_qty = max(1, int(per_level * random.uniform(0.5, 1.5)))

            book.add_liquidity("buy", bid_price, bid_qty)
            book.add_liquidity("sell", ask_price, ask_qty)

    def _generate_market_trades(
        self,
        book: SimulatedOrderBook,
        total_volume: int,
        now: datetime,
    ) -> None:
        """Generate market orders that cross the spread, creating trade ticks."""
        if total_volume <= 0:
            return

        # Split into 1-5 individual market orders
        num_orders = random.randint(1, 5)
        remaining = total_volume

        for i in range(num_orders):
            if remaining <= 0:
                break

            qty = remaining if i == num_orders - 1 else random.randint(1, max(1, remaining // 2))
            qty = min(qty, remaining)
            side = random.choice(["buy", "sell"])

            ticks = book.execute_market_order(side, qty, timestamp=now)
            # Mark all ticks as ambient
            for tick in ticks:
                tick.is_ambient = True
            self._trade_tape.record_ticks(ticks)
            remaining -= qty
