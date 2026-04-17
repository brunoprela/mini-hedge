"""Centralized order lifecycle event publications.

All ``orders.created`` / ``orders.filled`` / ``trades.*`` emissions funnel
through this publisher so OrderService stays focused on state transitions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from app.modules.orders.events import (
    order_created_data,
    order_filled_data,
    trade_executed_data,
)
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.modules.orders.models.order import OrderRecord
    from app.shared.events import EventBus


class OrderEventPublisher:
    """Thin façade over the event bus for order lifecycle events."""

    def __init__(self, *, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    async def publish_created(
        self,
        order: OrderRecord,
        event_type: AuditEventType,
        fund_slug: str,
    ) -> None:
        """Publish an ``orders.created`` event."""
        if self._event_bus is None:
            return
        event = BaseEvent(
            event_type=event_type,
            data=order_created_data(
                order_id=order.id,
                portfolio_id=str(order.portfolio_id),
                instrument_id=order.instrument_id,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                state=order.state,
            ),
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "orders.created"), event)

    async def publish_trade_decision(
        self,
        order: OrderRecord,
        event_type: AuditEventType,
        fund_slug: str,
    ) -> None:
        """Publish ``trades.approved`` or ``trades.rejected``."""
        if self._event_bus is None:
            return
        event = BaseEvent(
            event_type=event_type,
            data=trade_executed_data(
                portfolio_id=str(order.portfolio_id),
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                price=order.limit_price or Decimal("0"),
                trade_id=order.id,
            ),
            fund_slug=fund_slug,
        )
        is_approved = event_type == AuditEventType.TRADE_APPROVED
        topic_base = "trades.approved" if is_approved else "trades.rejected"
        await self._event_bus.publish(fund_topic(fund_slug, topic_base), event)

    async def publish_trade_executed(
        self,
        *,
        order: OrderRecord,
        trade_id: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        fund_slug: str,
    ) -> None:
        """Publish ``trades.executed`` with the correct buy/sell event_type."""
        if self._event_bus is None:
            return
        side = order.side
        event = BaseEvent(
            event_type=(
                AuditEventType.TRADE_BUY if side == "buy" else AuditEventType.TRADE_SELL
            ),
            data=trade_executed_data(
                portfolio_id=str(order.portfolio_id),
                instrument_id=order.instrument_id,
                side=side,
                quantity=fill_quantity,
                price=fill_price,
                trade_id=trade_id,
            ),
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "trades.executed"), event)

    async def publish_filled(
        self,
        *,
        order: OrderRecord,
        fill_quantity: Decimal,
        fill_price: Decimal,
        fund_slug: str,
    ) -> None:
        """Publish ``orders.filled`` after a successful fill."""
        if self._event_bus is None:
            return
        event = BaseEvent(
            event_type=AuditEventType.ORDER_FILLED,
            data=order_filled_data(
                order_id=order.id,
                portfolio_id=str(order.portfolio_id),
                instrument_id=order.instrument_id,
                side=order.side,
                fill_quantity=fill_quantity,
                fill_price=fill_price,
                state=order.state,
            ),
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "orders.filled"), event)

    async def publish_canceled(
        self,
        order: OrderRecord,
        fund_slug: str,
    ) -> None:
        """Publish a cancellation lifecycle event (currently reuses orders.created topic).

        Kept here for symmetry — OrderService doesn't emit a dedicated
        ``orders.canceled`` topic today, so this is a no-op placeholder.
        """
        return None
