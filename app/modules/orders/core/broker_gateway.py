"""Broker gateway — the single choke-point for broker-adapter interaction.

Centralizes broker-registry lookup + default-fallback logic so OrderService
doesn't have to juggle which adapter to use on every call. Future circuit-
breaker / retry instrumentation should live here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.modules.orders.core.broker_registry import BrokerRegistry
    from app.shared.adapters.broker import (
        BrokerAdapter,
        OrderAcknowledgement,
        OrderStatusReport,
    )

logger = structlog.get_logger()


class BrokerGateway:
    """Wraps broker adapters and the broker registry behind one interface."""

    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        broker_registry: BrokerRegistry | None = None,
    ) -> None:
        self._broker = broker
        self._broker_registry = broker_registry

    @property
    def default_broker(self) -> BrokerAdapter:
        return self._broker

    @property
    def registry(self) -> BrokerRegistry | None:
        return self._broker_registry

    def resolve(self, broker_id: str | None) -> BrokerAdapter:
        """Pick the adapter for a broker_id, falling back to the default."""
        if broker_id is None or self._broker_registry is None:
            return self._broker
        try:
            return self._broker_registry.get(broker_id)
        except KeyError:
            logger.warning("broker_not_in_registry", broker_id=broker_id)
            return self._broker

    async def submit(
        self,
        *,
        client_order_id: str,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        broker_id: str | None = None,
    ) -> OrderAcknowledgement:
        """Submit an order through the resolved broker adapter."""
        adapter = self.resolve(broker_id)
        return await adapter.submit_order(
            client_order_id=client_order_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
        )

    async def cancel(
        self, exchange_order_id: str, *, broker_id: str | None = None
    ) -> bool:
        adapter = self.resolve(broker_id)
        return await adapter.cancel_order(exchange_order_id)

    async def poll_status(
        self, exchange_order_id: str, *, broker_id: str | None = None
    ) -> OrderStatusReport:
        adapter = self.resolve(broker_id)
        return await adapter.get_order_status(exchange_order_id)
