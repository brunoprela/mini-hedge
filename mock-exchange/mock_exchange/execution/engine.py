"""Order execution engine — simulates broker fill behavior with order book.

Supports multiple broker profiles, order book-based fills, and market impact.
Fill behavior can be adjusted by the scenario engine to simulate market conditions.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from mock_exchange.execution.brokers import DEFAULT_BROKERS, BrokerProfile
from mock_exchange.execution.impact import MarketImpactModel
from mock_exchange.execution.trading_hours import is_market_open

if TYPE_CHECKING:
    from mock_exchange.market_data.order_book import SimulatedOrderBook
    from mock_exchange.market_data.service import MarketDataService
    from mock_exchange.market_data.trade_tape import TradeTape
    from mock_exchange.shared.kafka import MockExchangeProducer
    from mock_exchange.shared.models import InstrumentInfo

logger = structlog.get_logger()

EXECUTION_REPORTS_TOPIC = "shared.execution-reports"


class OrderStatus(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Fill:
    fill_id: str
    quantity: Decimal
    price: Decimal
    filled_at: datetime


@dataclass
class OrderState:
    exchange_order_id: str
    client_order_id: str
    instrument_id: str
    side: str
    order_type: str
    quantity: Decimal
    limit_price: Decimal | None
    status: OrderStatus
    broker_id: str = "GS"
    arrival_price: Decimal | None = None
    fills: list[Fill] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def filled_quantity(self) -> Decimal:
        return sum((f.quantity for f in self.fills), Decimal("0"))

    @property
    def avg_fill_price(self) -> Decimal | None:
        if not self.fills:
            return None
        total_value = sum(f.price * f.quantity for f in self.fills)
        total_qty = self.filled_quantity
        if total_qty == 0:
            return None
        return (total_value / total_qty).quantize(Decimal("0.0001"))


@dataclass
class ExecutionConfig:
    """Configurable fill behavior — adjusted by scenario engine."""

    fill_delay_ms: int = 50  # base delay before fill (broker-specific overrides)
    reject_rate: float = 0.0  # base rejection rate
    partial_fill_rate: float = 0.0  # base partial fill probability
    slippage_bps: float = 2.0  # fallback slippage when no order book
    trading_hours_enabled: bool = True  # reject orders outside market hours


class ExecutionEngine:
    """Manages orders and simulates broker fill behavior using order books."""

    def __init__(
        self,
        producer: MockExchangeProducer | None = None,
        market_data: MarketDataService | None = None,
        order_books: dict[str, SimulatedOrderBook] | None = None,
        trade_tape: TradeTape | None = None,
        impact_model: MarketImpactModel | None = None,
        instruments: dict[str, InstrumentInfo] | None = None,
        brokers: dict[str, BrokerProfile] | None = None,
    ) -> None:
        self._producer = producer
        self._market_data = market_data
        self._order_books = order_books or {}
        self._trade_tape = trade_tape
        self._impact_model = impact_model or MarketImpactModel()
        self._instruments = instruments or {}
        self._brokers = brokers or dict(DEFAULT_BROKERS)
        self._orders: dict[str, OrderState] = {}
        self._config = ExecutionConfig()
        self._fill_tasks: set[asyncio.Task[None]] = set()

    @property
    def config(self) -> ExecutionConfig:
        return self._config

    def update_config(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def submit_order(
        self,
        client_order_id: str,
        instrument_id: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        limit_price: Decimal | None = None,
        broker_id: str = "GS",
    ) -> OrderState:
        """Accept an order and schedule async fill processing."""
        exchange_order_id = str(uuid4())
        broker = self._brokers.get(broker_id)

        # Check trading hours for the instrument's exchange
        if self._config.trading_hours_enabled:
            instrument = self._instruments.get(instrument_id)
            if instrument and not is_market_open(instrument.exchange):
                order = OrderState(
                    exchange_order_id=exchange_order_id,
                    client_order_id=client_order_id,
                    instrument_id=instrument_id,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    limit_price=limit_price,
                    status=OrderStatus.REJECTED,
                    broker_id=broker_id,
                )
                self._orders[exchange_order_id] = order
                logger.info(
                    "order_rejected_market_closed",
                    exchange_order_id=exchange_order_id,
                    instrument_id=instrument_id,
                    exchange=instrument.exchange,
                )
                # Publish rejection to Kafka
                if self._producer:
                    self._producer.produce(
                        topic=EXECUTION_REPORTS_TOPIC,
                        event_type="execution.report",
                        data={
                            "exchange_order_id": exchange_order_id,
                            "client_order_id": client_order_id,
                            "instrument_id": instrument_id,
                            "side": side,
                            "status": "rejected",
                            "reject_reason": (
                                f"{instrument.exchange} is closed"
                            ),
                            "broker_id": broker_id,
                        },
                    )
                    self._producer.flush(timeout=0.5)
                return order

        # Capture arrival price from order book or market data
        arrival_price: Decimal | None = None
        book = self._order_books.get(instrument_id)
        if book:
            arrival_price = book.mid
        elif self._market_data:
            quote = self._market_data.get_latest_price(instrument_id)
            if quote:
                arrival_price = quote.mid

        # Check for rejection (broker-specific rate + base rate)
        reject_rate = self._config.reject_rate
        if broker:
            reject_rate = max(reject_rate, broker.reject_rate)

        if random.random() < reject_rate:
            order = OrderState(
                exchange_order_id=exchange_order_id,
                client_order_id=client_order_id,
                instrument_id=instrument_id,
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus.REJECTED,
                broker_id=broker_id,
                arrival_price=arrival_price,
            )
            self._orders[exchange_order_id] = order
            logger.info("order_rejected", exchange_order_id=exchange_order_id, broker_id=broker_id)
            return order

        order = OrderState(
            exchange_order_id=exchange_order_id,
            client_order_id=client_order_id,
            instrument_id=instrument_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            status=OrderStatus.ACKNOWLEDGED,
            broker_id=broker_id,
            arrival_price=arrival_price,
        )
        self._orders[exchange_order_id] = order

        # Schedule async fill
        task = asyncio.create_task(self._process_fill(order))
        self._fill_tasks.add(task)
        task.add_done_callback(self._fill_tasks.discard)

        return order

    async def _process_fill(self, order: OrderState) -> None:
        """Simulate fill after configurable delay."""
        try:
            await self._do_fill(order)
        except Exception:
            logger.exception(
                "fill_processing_failed",
                exchange_order_id=order.exchange_order_id,
            )

    async def _do_fill(self, order: OrderState) -> None:
        broker = self._brokers.get(order.broker_id)
        instrument = self._instruments.get(order.instrument_id)
        book = self._order_books.get(order.instrument_id)

        # Broker-specific latency
        delay_ms = broker.latency_ms if broker else self._config.fill_delay_ms
        await asyncio.sleep(delay_ms / 1000)

        # Determine fill quantity
        fill_qty = order.quantity
        fill_rate = broker.fill_rate if broker else (1.0 - self._config.partial_fill_rate)
        if random.random() > fill_rate:
            fill_qty = (order.quantity * Decimal(str(random.uniform(0.3, 0.8)))).quantize(
                Decimal("1")
            )
            fill_qty = max(fill_qty, Decimal("1"))

        # Check participation rate limits
        if broker and instrument and instrument.avg_daily_volume > 0:
            max_qty = int(broker.max_participation_rate * instrument.avg_daily_volume)
            if fill_qty > max_qty:
                fill_qty = Decimal(str(max_qty))

        # Execute against order book if available
        if book:
            fill_price, ticks = self._execute_via_book(
                book, order.side, order.order_type, fill_qty, order.limit_price, broker,
            )
            if ticks and self._trade_tape:
                self._trade_tape.record_ticks(ticks)

            # Apply market impact for large orders
            if instrument and self._impact_model and int(fill_qty) > 0:
                impact = self._impact_model.estimate_impact(
                    quantity=int(fill_qty),
                    adv=instrument.avg_daily_volume,
                    daily_volatility=instrument.annual_volatility,
                    side=order.side,
                )
                if impact.permanent_bps > 0.1:
                    new_mid = self._impact_model.apply_permanent_impact(
                        book.mid, impact.permanent_bps, order.side,
                    )
                    book.update_mid(new_mid)
        else:
            fill_price = self._compute_fallback_price(order, broker)

        fill = Fill(
            fill_id=str(uuid4()),
            quantity=fill_qty,
            price=fill_price,
            filled_at=datetime.now(UTC),
        )
        order.fills.append(fill)

        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        # Compute cost metrics for the execution report
        commission_bps = broker.commission_bps if broker else 5.0
        spread_cost_bps: float | None = None
        if order.arrival_price and order.arrival_price > 0:
            direction = Decimal("1") if order.side == "buy" else Decimal("-1")
            spread_cost_bps = float(
                direction * (fill_price - order.arrival_price) / order.arrival_price * 10000
            )

        logger.info(
            "order_filled",
            exchange_order_id=order.exchange_order_id,
            fill_price=str(fill_price),
            fill_qty=str(fill_qty),
            status=order.status,
            broker_id=order.broker_id,
        )

        # Publish execution report to Kafka
        if self._producer:
            self._producer.produce(
                topic=EXECUTION_REPORTS_TOPIC,
                event_type="execution.report",
                data={
                    "exchange_order_id": order.exchange_order_id,
                    "client_order_id": order.client_order_id,
                    "instrument_id": order.instrument_id,
                    "side": order.side,
                    "status": order.status,
                    "fill_id": fill.fill_id,
                    "fill_quantity": str(fill.quantity),
                    "fill_price": str(fill.price),
                    "filled_at": fill.filled_at.isoformat(),
                    "filled_quantity": str(order.filled_quantity),
                    "avg_fill_price": str(order.avg_fill_price) if order.avg_fill_price else None,
                    # Enhanced fields for multi-broker routing & TCA
                    "broker_id": order.broker_id,
                    "arrival_price": str(order.arrival_price) if order.arrival_price else None,
                    "commission_bps": commission_bps,
                    "spread_cost_bps": spread_cost_bps,
                },
            )
            self._producer.flush(timeout=0.5)

    def _execute_via_book(
        self,
        book: SimulatedOrderBook,
        side: str,
        order_type: str,
        quantity: Decimal,
        limit_price: Decimal | None,
        broker: BrokerProfile | None,
    ) -> tuple[Decimal, list]:
        """Execute an order against the order book."""

        qty = int(quantity)

        if order_type == "market" or limit_price is None:
            ticks = book.execute_market_order(side, qty)
        else:
            ticks, _resting = book.execute_limit_order(side, limit_price, qty)

        if not ticks:
            # No liquidity — use mid as fallback
            return book.mid, []

        # Compute VWAP across all tick fills
        total_value = sum(t.price * t.quantity for t in ticks)
        total_qty = sum(t.quantity for t in ticks)
        vwap_price = (total_value / total_qty).quantize(Decimal("0.0001"))

        # Apply broker spread markup
        if broker and broker.spread_markup_bps != 0:
            instrument = self._instruments.get(book.instrument_id)
            # Check for sector specialization bonus
            bonus = Decimal("0")
            if (
                instrument
                and broker.sector_specializations
                and instrument.sector in broker.sector_specializations
            ):
                bonus = Decimal(str(broker.specialization_bonus_bps))
            markup = Decimal(str(broker.spread_markup_bps)) - bonus
            direction = Decimal("1") if side == "buy" else Decimal("-1")
            adjustment = direction * markup / Decimal("10000")
            vwap_price = (vwap_price * (Decimal("1") + adjustment)).quantize(Decimal("0.0001"))

        return vwap_price, ticks

    def _compute_fallback_price(
        self, order: OrderState, broker: BrokerProfile | None,
    ) -> Decimal:
        """Fallback fill price when no order book is available."""
        base_price = order.limit_price
        if base_price is None and self._market_data:
            quote = self._market_data.get_latest_price(order.instrument_id)
            if quote:
                base_price = quote.mid
        if base_price is None:
            base_price = Decimal("100.00")

        # Apply slippage
        slippage_pct = Decimal(str(random.uniform(
            -self._config.slippage_bps / 10_000,
            self._config.slippage_bps / 10_000,
        )))
        return (base_price * (1 + slippage_pct)).quantize(Decimal("0.01"))

    def get_order(self, exchange_order_id: str) -> OrderState | None:
        return self._orders.get(exchange_order_id)

    def get_all_orders(self) -> list[OrderState]:
        """Return all orders (used by EOD reconciliation)."""
        return list(self._orders.values())

    def cancel_order(self, exchange_order_id: str) -> bool:
        order = self._orders.get(exchange_order_id)
        if order is None:
            return False
        if order.status in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED):
            return False
        order.status = OrderStatus.CANCELLED
        return True
