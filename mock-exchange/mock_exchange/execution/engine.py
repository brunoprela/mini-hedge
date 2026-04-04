"""Order execution engine — simulates broker fill behavior.

Supports configurable fill strategies: immediate, delayed, partial, reject.
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

if TYPE_CHECKING:
    from mock_exchange.market_data.service import MarketDataService
    from mock_exchange.shared.kafka import MockExchangeProducer

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

    fill_delay_ms: int = 50  # delay before fill
    reject_rate: float = 0.0  # probability of rejection (0.0-1.0)
    partial_fill_rate: float = 0.0  # probability of partial fill
    slippage_bps: float = 2.0  # slippage in basis points


class ExecutionEngine:
    """Manages orders and simulates broker fill behavior."""

    def __init__(
        self,
        producer: MockExchangeProducer | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self._producer = producer
        self._market_data = market_data
        self._orders: dict[str, OrderState] = {}
        self._config = ExecutionConfig()

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
    ) -> OrderState:
        """Accept an order and schedule async fill processing."""
        exchange_order_id = str(uuid4())

        # Check for rejection
        if random.random() < self._config.reject_rate:
            order = OrderState(
                exchange_order_id=exchange_order_id,
                client_order_id=client_order_id,
                instrument_id=instrument_id,
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus.REJECTED,
            )
            self._orders[exchange_order_id] = order
            logger.info("order_rejected", exchange_order_id=exchange_order_id)
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
        )
        self._orders[exchange_order_id] = order

        # Schedule async fill
        asyncio.create_task(self._process_fill(order))

        return order

    async def _process_fill(self, order: OrderState) -> None:
        """Simulate fill after configurable delay."""
        await asyncio.sleep(self._config.fill_delay_ms / 1000)

        # Determine fill price
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
        fill_price = (base_price * (1 + slippage_pct)).quantize(Decimal("0.01"))

        # Determine fill quantity (partial or full)
        if random.random() < self._config.partial_fill_rate:
            fill_qty = (order.quantity * Decimal(str(random.uniform(0.3, 0.8)))).quantize(
                Decimal("1")
            )
            fill_qty = max(fill_qty, Decimal("1"))
        else:
            fill_qty = order.quantity

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

        logger.info(
            "order_filled",
            exchange_order_id=order.exchange_order_id,
            fill_price=str(fill_price),
            fill_qty=str(fill_qty),
            status=order.status,
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
                },
            )
            self._producer.flush(timeout=0.5)

    def get_order(self, exchange_order_id: str) -> OrderState | None:
        return self._orders.get(exchange_order_id)

    def cancel_order(self, exchange_order_id: str) -> bool:
        order = self._orders.get(exchange_order_id)
        if order is None:
            return False
        if order.status in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED):
            return False
        order.status = OrderStatus.CANCELLED
        return True
