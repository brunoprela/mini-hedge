"""Shared test helpers — EventCapture spy, StubBroker, event factories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from app.shared.adapters import OrderAcknowledgement, OrderStatusReport

if TYPE_CHECKING:
    from app.shared.events import BaseEvent, EventHandler, InProcessEventBus

# ---------------------------------------------------------------------------
# EventCapture — spy that records all events flowing through the bus
# ---------------------------------------------------------------------------


@dataclass
class CapturedEvent:
    topic: str
    event: BaseEvent


class EventCapture:
    """Subscribe to EventBus topics to record all published events.

    Usage::

        capture = EventCapture()
        capture.wire_to_bus(bus, fund_topics_for_slug("alpha") + shared_topics())

        # ... run code that publishes events ...

        assert len(capture.get_by_topic("trades.executed")) == 1
        assert capture.get_by_type("trade.buy")[0].data["instrument_id"] == "AAPL"
    """

    def __init__(self) -> None:
        self.events: list[CapturedEvent] = []

    def wire_to_bus(self, bus: InProcessEventBus, topics: list[str]) -> None:
        """Subscribe a capture handler to every topic in *topics*."""
        for topic in topics:
            bus.subscribe(topic, self._make_handler(topic))

    def _make_handler(self, topic: str) -> EventHandler:
        async def handler(event: BaseEvent) -> None:
            self.events.append(CapturedEvent(topic=topic, event=event))

        return handler

    # -- query helpers -----------------------------------------------------

    def get_by_topic(self, topic_substring: str) -> list[BaseEvent]:
        """Return events whose topic contains *topic_substring*."""
        return [ce.event for ce in self.events if topic_substring in ce.topic]

    def get_by_type(self, event_type: str) -> list[BaseEvent]:
        """Return events matching *event_type* exactly."""
        return [ce.event for ce in self.events if ce.event.event_type == event_type]

    def topics(self) -> list[str]:
        """Return the ordered list of topics that received events."""
        return [ce.topic for ce in self.events]

    def clear(self) -> None:
        self.events.clear()


# ---------------------------------------------------------------------------
# StubBroker — deterministic BrokerAdapter for tests
# ---------------------------------------------------------------------------


class StubBroker:
    """BrokerAdapter that fills immediately at the limit price.

    Deterministic: no randomness, no delays, no rejects.
    """

    def __init__(self, default_price: Decimal = Decimal("100.00")) -> None:
        self._default_price = default_price
        self._fills: dict[str, tuple[Decimal, Decimal]] = {}

    async def submit_order(
        self,
        client_order_id: str,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
    ) -> OrderAcknowledgement:
        price = limit_price or self._default_price
        exchange_id = str(uuid4())
        self._fills[exchange_id] = (price, quantity)
        return OrderAcknowledgement(
            exchange_order_id=exchange_id,
            client_order_id=client_order_id,
            status="filled",
            received_at=datetime.now(UTC),
        )

    async def cancel_order(self, exchange_order_id: str) -> bool:
        return False

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusReport:
        price, qty = self._fills.get(exchange_order_id, (Decimal(0), Decimal(0)))
        return OrderStatusReport(
            exchange_order_id=exchange_order_id,
            client_order_id="",
            status="filled",
            filled_quantity=qty,
            avg_fill_price=price,
        )
