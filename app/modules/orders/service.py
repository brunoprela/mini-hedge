"""Order lifecycle service — orchestrates compliance, broker, and events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.compliance.interface import TradeCheckRequest
from app.modules.orders.interface import (
    CreateOrderRequest,
    FillDetail,
    OrderState,
    OrderSummary,
)
from app.modules.orders.models import OrderFillRecord, OrderRecord
from app.modules.orders.state_machine import apply_transition
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.modules.orders.compliance_gateway import ComplianceGateway
    from app.modules.orders.mock_broker import MockBrokerAdapter
    from app.modules.orders.repository import OrderRepository
    from app.modules.platform.audit_repository import AuditLogRepository
    from app.shared.events import EventBus

logger = structlog.get_logger()


class OrderService:
    """Manages the full order lifecycle with compliance integration."""

    def __init__(
        self,
        order_repo: OrderRepository,
        compliance_gateway: ComplianceGateway,
        mock_broker: MockBrokerAdapter,
        event_bus: EventBus,
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self._repo = order_repo
        self._compliance = compliance_gateway
        self._broker = mock_broker
        self._event_bus = event_bus
        self._audit = audit_repo

    async def create_order(
        self,
        request: CreateOrderRequest,
        fund_slug: str,
        actor_id: str,
    ) -> OrderSummary:
        """Create and process an order through the full lifecycle."""
        # 1. Create order in DRAFT state
        order = OrderRecord(
            id=str(uuid4()),
            portfolio_id=str(request.portfolio_id),
            instrument_id=request.instrument_id,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            filled_quantity=Decimal(0),
            limit_price=request.limit_price,
            state=OrderState.DRAFT.value,
            time_in_force=request.time_in_force.value,
            fund_slug=fund_slug,
        )
        order = await self._repo.save(order)

        # 2. Transition to PENDING_COMPLIANCE
        apply_transition(OrderState(order.state), OrderState.PENDING_COMPLIANCE)
        order = await self._repo.update_state(UUID(order.id), OrderState.PENDING_COMPLIANCE.value)

        # 3. Run compliance check
        check_request = TradeCheckRequest(
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            side=request.side.value,
            quantity=request.quantity,
            price=request.limit_price or Decimal("100.00"),
        )
        decision = await self._compliance.check(check_request, fund_slug)

        compliance_data = [
            {
                "rule_id": str(r.rule_id),
                "rule_name": r.rule_name,
                "passed": r.passed,
                "severity": r.severity,
                "message": r.message,
            }
            for r in decision.results
        ]

        if not decision.approved:
            # 4a. Rejected
            apply_transition(OrderState(order.state), OrderState.REJECTED)
            reason = "; ".join(decision.blocked_by)
            order = await self._repo.update_state(
                UUID(order.id),
                OrderState.REJECTED.value,
                rejection_reason=reason,
                compliance_results=compliance_data,
            )
            logger.info(
                "order_rejected",
                order_id=order.id,
                reason=reason,
            )
            await self._audit_event(
                "order.rejected",
                actor_id=actor_id,
                fund_slug=fund_slug,
                order=order,
                extra={"rejection_reason": reason, "compliance_results": compliance_data},
            )
            return self._to_summary(order)

        # 4b. Approved
        apply_transition(OrderState(order.state), OrderState.APPROVED)
        order = await self._repo.update_state(
            UUID(order.id),
            OrderState.APPROVED.value,
            compliance_results=compliance_data,
        )

        # 5. Transition to SENT and submit to broker
        apply_transition(OrderState(order.state), OrderState.SENT)
        order = await self._repo.update_state(UUID(order.id), OrderState.SENT.value)

        fill_price, fill_qty = await self._broker.submit_order(
            instrument_id=request.instrument_id,
            side=request.side.value,
            quantity=request.quantity,
            price=request.limit_price,
        )

        # 6. Process fill
        order = await self._process_fill(order, fill_price, fill_qty, fund_slug)

        logger.info(
            "order_filled",
            order_id=order.id,
            fill_price=str(fill_price),
            fill_qty=str(fill_qty),
        )
        await self._audit_event(
            "order.filled",
            actor_id=actor_id,
            fund_slug=fund_slug,
            order=order,
            extra={
                "fill_price": str(fill_price),
                "fill_quantity": str(fill_qty),
                "compliance_results": compliance_data,
            },
        )
        return self._to_summary(order)

    async def cancel_order(
        self, order_id: UUID, actor_id: str = "system"
    ) -> OrderSummary:
        """Cancel an order if transition is valid."""
        order = await self._repo.get_by_id(order_id)
        if order is None:
            raise LookupError(f"Order {order_id} not found")

        apply_transition(OrderState(order.state), OrderState.CANCELLED)
        order = await self._repo.update_state(order_id, OrderState.CANCELLED.value)
        await self._audit_event(
            "order.cancelled",
            actor_id=actor_id,
            fund_slug=order.fund_slug,
            order=order,
        )
        return self._to_summary(order)

    async def get_order(self, order_id: UUID) -> OrderSummary:
        """Get a single order by ID."""
        order = await self._repo.get_by_id(order_id)
        if order is None:
            raise LookupError(f"Order {order_id} not found")
        return self._to_summary(order)

    async def get_orders(
        self,
        portfolio_id: UUID,
        state: str | None = None,
    ) -> list[OrderSummary]:
        """List orders for a portfolio, optionally filtered by state."""
        records = await self._repo.get_by_portfolio(portfolio_id, state=state)
        return [self._to_summary(r) for r in records]

    async def get_fills(self, order_id: UUID) -> list[FillDetail]:
        """Get fill details for an order."""
        fills = await self._repo.get_fills(order_id)
        return [
            FillDetail(
                id=UUID(f.id),
                order_id=UUID(f.order_id),
                quantity=f.quantity,
                price=f.price,
                filled_at=f.filled_at,
            )
            for f in fills
        ]

    async def _process_fill(
        self,
        order: OrderRecord,
        fill_price: Decimal,
        fill_quantity: Decimal,
        fund_slug: str,
    ) -> OrderRecord:
        """Record a fill and publish a trade event."""
        trade_id = uuid4()
        now = datetime.now(UTC)

        # Create fill record
        fill = OrderFillRecord(
            id=str(trade_id),
            order_id=order.id,
            quantity=fill_quantity,
            price=fill_price,
            filled_at=now,
        )
        await self._repo.save_fill(fill)

        # Update order state
        new_filled = order.filled_quantity + fill_quantity
        if new_filled >= order.quantity:
            target_state = OrderState.FILLED
        else:
            target_state = OrderState.PARTIALLY_FILLED

        # Compute VWAP across all fills
        if order.filled_quantity > 0 and order.avg_fill_price is not None:
            avg_price = (
                order.avg_fill_price * order.filled_quantity + fill_price * fill_quantity
            ) / new_filled
        else:
            avg_price = fill_price

        apply_transition(OrderState(order.state), target_state)
        order = await self._repo.update_state(
            UUID(order.id),
            target_state.value,
            filled_quantity=new_filled,
            avg_fill_price=avg_price,
        )

        # Publish trade event so positions module picks it up
        side = order.side
        event = BaseEvent(
            event_type=("trade.buy" if side == "buy" else "trade.sell"),
            data={
                "portfolio_id": str(order.portfolio_id),
                "instrument_id": order.instrument_id,
                "side": side,
                "quantity": str(fill_quantity),
                "price": str(fill_price),
                "trade_id": str(trade_id),
                "currency": "USD",
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "trades.executed"), event)

        return order

    async def _audit_event(
        self,
        event_type: str,
        *,
        actor_id: str,
        fund_slug: str,
        order: OrderRecord,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._audit is None:
            return
        payload: dict[str, object] = {
            "order_id": order.id,
            "portfolio_id": order.portfolio_id,
            "instrument_id": order.instrument_id,
            "side": order.side,
            "quantity": str(order.quantity),
            "state": order.state,
        }
        if extra:
            payload.update(extra)
        await self._audit.insert_admin_event(
            event_type=event_type,
            actor_id=actor_id,
            actor_type="user",
            fund_slug=fund_slug,
            payload=payload,
        )

    @staticmethod
    def _to_summary(record: OrderRecord) -> OrderSummary:
        """Convert an OrderRecord to an OrderSummary."""
        return OrderSummary(
            id=UUID(record.id),
            portfolio_id=UUID(record.portfolio_id),
            instrument_id=record.instrument_id,
            side=record.side,
            order_type=record.order_type,
            quantity=record.quantity,
            filled_quantity=record.filled_quantity,
            limit_price=record.limit_price,
            avg_fill_price=record.avg_fill_price,
            state=record.state,
            rejection_reason=record.rejection_reason,
            compliance_results=record.compliance_results,
            time_in_force=record.time_in_force,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
