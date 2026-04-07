"""Order lifecycle service — orchestrates compliance, broker, and events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.compliance.interface import TradeCheckRequest
from app.modules.orders.interface import (
    CreateAlgoOrderRequest,
    CreateOrderRequest,
    FillDetail,
    OrderState,
    OrderSummary,
)
from app.modules.orders.models import OrderFillRecord, OrderRecord
from app.modules.orders.state_machine import apply_transition, derive_parent_state
from app.shared.audit_events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.market_data.service import MarketDataService
    from app.modules.orders.algo.engine import AlgoEngine
    from app.modules.orders.broker_registry import BrokerRegistry
    from app.modules.orders.compliance_gateway import ComplianceGateway
    from app.modules.orders.repository import OrderRepository
    from app.modules.orders.routing_engine import RoutingEngine
    from app.modules.orders.scorecard_service import ScorecardService
    from app.modules.orders.tca.service import TCAService
    from app.modules.platform.audit_repository import AuditLogRepository
    from app.shared.adapters import BrokerAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


class OrderService:
    """Manages the full order lifecycle with compliance integration."""

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        order_repo: OrderRepository,
        compliance_gateway: ComplianceGateway,
        broker: BrokerAdapter,
        event_bus: EventBus,
        audit_repo: AuditLogRepository | None = None,
        broker_registry: BrokerRegistry | None = None,
        routing_engine: RoutingEngine | None = None,
        scorecard_service: ScorecardService | None = None,
        market_data_service: MarketDataService | None = None,
        tca_service: TCAService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._order_repo = order_repo
        self._compliance_gateway = compliance_gateway
        self._broker = broker
        self._event_bus = event_bus
        self._audit_repo = audit_repo
        self._fund_slugs: list[str] = []  # Set by setup code; used to locate orders across schemas
        self._algo_engine: AlgoEngine | None = None  # Set by setup code after AlgoEngine is created
        self._broker_registry = broker_registry
        self._routing_engine = routing_engine
        self._scorecard_service = scorecard_service
        self._market_data_service = market_data_service
        self._tca_service = tca_service

    async def create_order(
        self,
        request: CreateOrderRequest,
        fund_slug: str,
        actor_id: str,
        *,
        session: AsyncSession | None = None,
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
        # Capture arrival price from in-memory market data cache
        if self._market_data_service is not None:
            snap = await self._market_data_service.get_latest_price(request.instrument_id)
            if snap is not None:
                order.arrival_mid_price = snap.mid
                order.arrival_spread = snap.ask - snap.bid
                order.arrival_timestamp = snap.timestamp

        order = await self._order_repo.save(order, session=session)

        # 2. Transition to PENDING_COMPLIANCE
        apply_transition(OrderState(order.state), OrderState.PENDING_COMPLIANCE)
        order = await self._order_repo.update_state(
            UUID(order.id), OrderState.PENDING_COMPLIANCE.value, session=session
        )

        # 3. Run compliance check
        check_request = TradeCheckRequest(
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            side=request.side.value,
            quantity=request.quantity,
            price=request.limit_price or Decimal("100.00"),
        )
        decision = await self._compliance_gateway.check(check_request)

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
            order = await self._order_repo.update_state(
                UUID(order.id),
                OrderState.REJECTED.value,
                rejection_reason=reason,
                compliance_results=compliance_data,
                session=session,
            )
            logger.info(
                "order_rejected",
                order_id=order.id,
                reason=reason,
            )
            await self._publish_order_event(order, AuditEventType.ORDER_CREATED, fund_slug)
            await self._publish_trade_decision(order, AuditEventType.TRADE_REJECTED, fund_slug)
            await self._audit_event(
                AuditEventType.ORDER_REJECTED,
                actor_id=actor_id,
                fund_slug=fund_slug,
                order=order,
                extra={"rejection_reason": reason, "compliance_results": compliance_data},
                session=session,
            )
            return self._to_summary(order)

        # 4b. Approved
        apply_transition(OrderState(order.state), OrderState.APPROVED)
        order = await self._order_repo.update_state(
            UUID(order.id),
            OrderState.APPROVED.value,
            compliance_results=compliance_data,
            session=session,
        )
        await self._publish_order_event(order, AuditEventType.ORDER_CREATED, fund_slug)
        await self._publish_trade_decision(order, AuditEventType.TRADE_APPROVED, fund_slug)

        # 5. Route to broker(s) via routing engine
        broker_id: str | None = None
        broker_to_use = self._broker

        if self._routing_engine and self._broker_registry:
            slices = await self._routing_engine.route_order(
                order_id=order.id,
                instrument_id=request.instrument_id,
                instrument_class=None,
                side=request.side.value,
                quantity=request.quantity,
                order_type=request.order_type.value,
                fund_slug=fund_slug,
            )
            if len(slices) == 1:
                broker_id = slices[0].broker_id
                try:
                    broker_to_use = self._broker_registry.get(broker_id)
                except KeyError:
                    broker_to_use = self._broker
            # TODO: multi-broker split creates child orders (future enhancement)

        # 6. Transition to SENT and submit to broker
        apply_transition(OrderState(order.state), OrderState.SENT)
        order = await self._order_repo.update_state(
            UUID(order.id),
            OrderState.SENT.value,
            broker_id=broker_id,
            session=session,
        )

        ack = await broker_to_use.submit_order(
            client_order_id=order.id,
            instrument_id=request.instrument_id,
            side=request.side.value,
            quantity=request.quantity,
            order_type=request.order_type.value,
            limit_price=request.limit_price,
        )

        if ack.status == "filled":
            # Synchronous fill (in-process adapter) — query fill details and process
            status_report = await broker_to_use.get_order_status(ack.exchange_order_id)
            fill_price = status_report.avg_fill_price or Decimal("0")
            fill_qty = status_report.filled_quantity
            order = await self._process_fill(
                order,
                fill_price,
                fill_qty,
                fund_slug,
                broker_id=broker_id,
                session=session,
            )

            logger.info(
                "order_filled",
                order_id=order.id,
                fill_price=str(fill_price),
                fill_qty=str(fill_qty),
                broker_id=broker_id,
            )
            await self._audit_event(
                AuditEventType.ORDER_FILLED,
                actor_id=actor_id,
                fund_slug=fund_slug,
                order=order,
                extra={
                    "fill_price": str(fill_price),
                    "fill_quantity": str(fill_qty),
                    "compliance_results": compliance_data,
                    "broker_id": broker_id,
                },
                session=session,
            )
        else:
            # Async fill (mock-exchange, FIX, etc.) — order stays in SENT state.
            # Fills arrive later via execution report callback.
            logger.info(
                "order_sent_to_broker",
                order_id=order.id,
                exchange_order_id=ack.exchange_order_id,
                status=ack.status,
                broker_id=broker_id,
            )

        return self._to_summary(order)

    async def create_algo_order(
        self,
        request: CreateAlgoOrderRequest,
        fund_slug: str,
        actor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> OrderSummary:
        """Create a parent algo order, compliance-check it, and start the algo engine."""
        if self._algo_engine is None:
            msg = "AlgoEngine not configured"
            raise RuntimeError(msg)

        # 1. Create parent order in DRAFT state
        parent = OrderRecord(
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
            is_parent=True,
            algo_type=request.algo_type.value,
            algo_params=request.algo_params.model_dump(),
        )
        # Capture arrival price from in-memory market data cache
        if self._market_data_service is not None:
            snap = await self._market_data_service.get_latest_price(request.instrument_id)
            if snap is not None:
                parent.arrival_mid_price = snap.mid
                parent.arrival_spread = snap.ask - snap.bid
                parent.arrival_timestamp = snap.timestamp

        parent = await self._order_repo.save(parent, session=session)

        # 2. Compliance check (once for the parent — children inherit)
        apply_transition(OrderState(parent.state), OrderState.PENDING_COMPLIANCE)
        parent = await self._order_repo.update_state(
            UUID(parent.id), OrderState.PENDING_COMPLIANCE.value, session=session
        )

        check_request = TradeCheckRequest(
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            side=request.side.value,
            quantity=request.quantity,
            price=request.limit_price or Decimal("100.00"),
        )
        decision = await self._compliance_gateway.check(check_request)

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
            apply_transition(OrderState(parent.state), OrderState.REJECTED)
            reason = "; ".join(decision.blocked_by)
            parent = await self._order_repo.update_state(
                UUID(parent.id),
                OrderState.REJECTED.value,
                rejection_reason=reason,
                compliance_results=compliance_data,
                session=session,
            )
            await self._publish_order_event(parent, AuditEventType.ORDER_CREATED, fund_slug)
            await self._publish_trade_decision(parent, AuditEventType.TRADE_REJECTED, fund_slug)
            await self._audit_event(
                AuditEventType.ORDER_REJECTED,
                actor_id=actor_id,
                fund_slug=fund_slug,
                order=parent,
                extra={"rejection_reason": reason, "compliance_results": compliance_data},
                session=session,
            )
            return self._to_summary(parent)

        # 3. Approved → transition to WORKING and start algo
        apply_transition(OrderState(parent.state), OrderState.APPROVED)
        parent = await self._order_repo.update_state(
            UUID(parent.id),
            OrderState.APPROVED.value,
            compliance_results=compliance_data,
            session=session,
        )
        await self._publish_order_event(parent, AuditEventType.ORDER_CREATED, fund_slug)
        await self._publish_trade_decision(parent, AuditEventType.TRADE_APPROVED, fund_slug)

        apply_transition(OrderState(parent.state), OrderState.WORKING)
        parent = await self._order_repo.update_state(
            UUID(parent.id), OrderState.WORKING.value, session=session
        )

        # 4. Start algo engine — spawns child orders over time
        await self._algo_engine.start_algo(parent, fund_slug)

        await self._audit_event(
            AuditEventType.ORDER_CREATED,
            actor_id=actor_id,
            fund_slug=fund_slug,
            order=parent,
            extra={
                "algo_type": request.algo_type.value,
                "algo_params": request.algo_params.model_dump(),
                "compliance_results": compliance_data,
            },
            session=session,
        )
        return self._to_summary(parent)

    async def create_child_order(
        self,
        *,
        parent_order_id: str,
        quantity: Decimal,
        fund_slug: str,
        limit_price: Decimal | None = None,
    ) -> OrderSummary:
        """Create and immediately send a child order. Called by AlgoEngine.

        Children inherit the parent's compliance approval — no separate check.
        """
        parent = await self._order_repo.get_by_id(UUID(parent_order_id))
        if parent is None:
            msg = f"Parent order {parent_order_id} not found"
            raise LookupError(msg)

        child = OrderRecord(
            id=str(uuid4()),
            portfolio_id=parent.portfolio_id,
            instrument_id=parent.instrument_id,
            side=parent.side,
            order_type=parent.order_type,
            quantity=quantity,
            filled_quantity=Decimal(0),
            limit_price=limit_price or parent.limit_price,
            state=OrderState.DRAFT.value,
            time_in_force=parent.time_in_force,
            fund_slug=fund_slug,
            parent_order_id=parent_order_id,
        )
        child = await self._order_repo.save(child)

        # Skip compliance — inherited from parent. DRAFT → APPROVED → SENT
        apply_transition(OrderState(child.state), OrderState.PENDING_COMPLIANCE)
        apply_transition(OrderState.PENDING_COMPLIANCE, OrderState.APPROVED)
        child = await self._order_repo.update_state(UUID(child.id), OrderState.APPROVED.value)

        apply_transition(OrderState(child.state), OrderState.SENT)
        child = await self._order_repo.update_state(UUID(child.id), OrderState.SENT.value)

        # Submit to broker
        ack = await self._broker.submit_order(
            client_order_id=child.id,
            instrument_id=parent.instrument_id,
            side=parent.side,
            quantity=quantity,
            order_type=parent.order_type,
            limit_price=limit_price or parent.limit_price,
        )

        if ack.status == "filled":
            status_report = await self._broker.get_order_status(ack.exchange_order_id)
            fill_price = status_report.avg_fill_price or Decimal("0")
            fill_qty = status_report.filled_quantity
            child = await self._process_fill(child, fill_price, fill_qty, fund_slug)

        return self._to_summary(child)

    _FILL_RETRY_DELAYS = (0.1, 0.3, 1.0)  # seconds — handles race with order commit

    async def process_execution_report(
        self,
        client_order_id: str,
        fill_price: Decimal,
        fill_quantity: Decimal,
        filled_at: datetime | None = None,
        broker_id: str | None = None,
    ) -> None:
        """Handle an async fill from an external broker.

        Called by the broker adapter's execution report consumer when a fill
        arrives on the vendor's Kafka. This is the async counterpart to the
        synchronous fill path in create_order.

        Retries lookup briefly to handle the race where a fill arrives before
        the order row is committed (fill_delay_ms can be very low).
        """
        import asyncio

        # Search across all fund schemas to find the order.
        # This runs outside a request context, so we don't know which fund
        # the order belongs to. The number of funds is small (<50).
        order = None
        fund_slug = None

        for attempt_delay in self._FILL_RETRY_DELAYS:
            for slug in self._fund_slugs:
                async with self._session_factory.fund_scope(slug):
                    found = await self._order_repo.get_by_id(UUID(client_order_id))
                if found is not None:
                    order = found
                    fund_slug = slug
                    break
            if order is not None:
                break
            await asyncio.sleep(attempt_delay)

        if order is None or fund_slug is None:
            logger.warning(
                "execution_report_unknown_order",
                client_order_id=client_order_id,
            )
            return

        if order.state not in (OrderState.SENT.value, OrderState.PARTIALLY_FILLED.value):
            logger.warning(
                "execution_report_invalid_state",
                order_id=order.id,
                state=order.state,
            )
            return

        async with self._session_factory.fund_scope(fund_slug):
            order = await self._process_fill(
                order,
                fill_price,
                fill_quantity,
                fund_slug,
                broker_id=broker_id,
                filled_at=filled_at,
            )

        logger.info(
            "order_filled_async",
            order_id=order.id,
            fill_price=str(fill_price),
            fill_qty=str(fill_quantity),
            state=order.state,
        )
        await self._audit_event(
            AuditEventType.ORDER_FILLED,
            actor_id="broker",
            fund_slug=fund_slug,
            order=order,
            extra={
                "fill_price": str(fill_price),
                "fill_quantity": str(fill_quantity),
                "source": "execution_report",
            },
        )

    async def cancel_order(
        self, order_id: UUID, actor_id: str = "system", *, session: AsyncSession | None = None
    ) -> OrderSummary:
        """Cancel an order. For parent orders, also cancels the algo and children."""
        order = await self._order_repo.get_by_id(order_id, session=session)
        if order is None:
            raise LookupError(f"Order {order_id} not found")

        # If this is a parent algo order, stop the algo engine and cancel children
        if order.is_parent and self._algo_engine is not None:
            await self._algo_engine.cancel_algo(order_id)
            active_children = await self._order_repo.get_active_children(order_id, session=session)
            for child in active_children:
                try:
                    apply_transition(OrderState(child.state), OrderState.CANCELLED)
                    await self._order_repo.update_state(
                        UUID(child.id), OrderState.CANCELLED.value, session=session
                    )
                except Exception:
                    logger.warning("child_cancel_failed", child_id=child.id, state=child.state)

        apply_transition(OrderState(order.state), OrderState.CANCELLED)
        order = await self._order_repo.update_state(
            order_id, OrderState.CANCELLED.value, session=session
        )
        await self._audit_event(
            AuditEventType.ORDER_CANCELLED,
            actor_id=actor_id,
            fund_slug=order.fund_slug,
            order=order,
            session=session,
        )
        return self._to_summary(order)

    async def get_order(
        self, order_id: UUID, *, session: AsyncSession | None = None
    ) -> OrderSummary:
        """Get a single order by ID."""
        order = await self._order_repo.get_by_id(order_id, session=session)
        if order is None:
            raise LookupError(f"Order {order_id} not found")
        return self._to_summary(order)

    async def get_orders(
        self,
        portfolio_id: UUID,
        state: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderSummary]:
        """List orders for a portfolio, optionally filtered by state."""
        records = await self._order_repo.get_by_portfolio(
            portfolio_id, state=state, session=session
        )
        return [self._to_summary(r) for r in records]

    async def get_children(
        self, parent_order_id: UUID, *, session: AsyncSession | None = None
    ) -> list[OrderSummary]:
        """List child orders for a parent algo order."""
        records = await self._order_repo.get_children(parent_order_id, session=session)
        return [self._to_summary(r) for r in records]

    async def get_fills(
        self, order_id: UUID, *, session: AsyncSession | None = None
    ) -> list[FillDetail]:
        """Get fill details for an order."""
        fills = await self._order_repo.get_fills(order_id, session=session)
        return [
            FillDetail(
                id=UUID(f.id),
                order_id=UUID(f.order_id),
                quantity=f.quantity,
                price=f.price,
                broker_id=f.broker_id,
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
        *,
        broker_id: str | None = None,
        filled_at: datetime | None = None,
        session: AsyncSession | None = None,
    ) -> OrderRecord:
        """Record a fill and publish a trade event."""
        trade_id = uuid4()
        now = filled_at or datetime.now(UTC)

        # Use broker_id from order if not explicitly passed
        effective_broker_id = broker_id or order.broker_id

        # Create fill record
        fill = OrderFillRecord(
            id=str(trade_id),
            order_id=order.id,
            quantity=fill_quantity,
            price=fill_price,
            broker_id=effective_broker_id,
            filled_at=now,
        )
        await self._order_repo.save_fill(fill, session=session)

        # Update broker scorecard (fire-and-forget)
        if self._scorecard_service and effective_broker_id:
            try:
                slippage = Decimal("0")
                commission = Decimal("5")  # default 5 bps
                await self._scorecard_service.record_fill(
                    broker_id=effective_broker_id,
                    slippage_bps=slippage,
                    fill_time_ms=0,
                    commission_bps=commission,
                    fund_slug=fund_slug,
                )
            except Exception:
                logger.exception("scorecard_update_failed")

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
        order = await self._order_repo.update_state(
            UUID(order.id),
            target_state.value,
            filled_quantity=new_filled,
            avg_fill_price=avg_price,
            session=session,
        )

        # Publish trade event — TradeHandler subscribes and creates the
        # position (event-sourced).  Downstream cascade (exposure, risk,
        # compliance, cash) reacts to positions.changed / trades.executed.
        side = order.side
        event = BaseEvent(
            event_type=(AuditEventType.TRADE_BUY if side == "buy" else AuditEventType.TRADE_SELL),
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

        # Publish order fill event
        fill_event = BaseEvent(
            event_type=AuditEventType.ORDER_FILLED,
            data={
                "order_id": order.id,
                "portfolio_id": str(order.portfolio_id),
                "instrument_id": order.instrument_id,
                "side": side,
                "fill_quantity": str(fill_quantity),
                "fill_price": str(fill_price),
                "state": order.state,
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "orders.filled"), fill_event)

        # Trigger TCA computation when order is fully filled
        if target_state == OrderState.FILLED and self._tca_service is not None:
            import asyncio

            asyncio.create_task(
                self._tca_service.compute_for_order(UUID(order.id)),
                name=f"tca-{order.id}",
            )

        # If this is a child order, update the parent's aggregate state
        if order.parent_order_id is not None:
            await self._update_parent_from_children(
                UUID(order.parent_order_id), fund_slug, session=session
            )
            # Notify algo engine for Iceberg replenishment
            if self._algo_engine is not None:
                await self._algo_engine.on_child_filled(order, fund_slug)

        return order

    async def _update_parent_from_children(
        self,
        parent_order_id: UUID,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Recompute parent order state from its children's aggregate states."""
        parent = await self._order_repo.get_by_id(parent_order_id, session=session)
        if parent is None:
            return

        children = await self._order_repo.get_children(parent_order_id, session=session)
        if not children:
            return

        child_states = [OrderState(c.state) for c in children]
        new_state = derive_parent_state(child_states)

        # Aggregate fill quantities and compute VWAP across all children
        total_filled = sum((c.filled_quantity for c in children), Decimal(0))
        total_cost = sum(
            (
                c.filled_quantity * c.avg_fill_price
                for c in children
                if c.avg_fill_price is not None and c.filled_quantity > 0
            ),
            Decimal(0),
        )
        avg_price: Decimal | None = (total_cost / total_filled) if total_filled > 0 else None

        current_state = OrderState(parent.state)
        if new_state != current_state:
            try:
                apply_transition(current_state, new_state)
            except Exception:
                logger.warning(
                    "parent_state_transition_skipped",
                    parent_order_id=str(parent_order_id),
                    current=current_state,
                    target=new_state,
                )
                return

        await self._order_repo.update_state(
            parent_order_id,
            new_state.value,
            filled_quantity=total_filled,
            avg_fill_price=avg_price,
            session=session,
        )

    async def _publish_order_event(
        self,
        order: OrderRecord,
        event_type: AuditEventType,
        fund_slug: str,
    ) -> None:
        """Publish an order lifecycle event to Kafka."""
        event = BaseEvent(
            event_type=event_type,
            data={
                "order_id": order.id,
                "portfolio_id": str(order.portfolio_id),
                "instrument_id": order.instrument_id,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": str(order.quantity),
                "state": order.state,
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "orders.created"), event)

    async def _publish_trade_decision(
        self,
        order: OrderRecord,
        event_type: AuditEventType,
        fund_slug: str,
    ) -> None:
        """Publish trade.approved or trade.rejected event."""
        event = BaseEvent(
            event_type=event_type,
            data={
                "portfolio_id": str(order.portfolio_id),
                "instrument_id": order.instrument_id,
                "side": order.side,
                "quantity": str(order.quantity),
                "price": str(order.limit_price or Decimal("0")),
                "trade_id": order.id,
                "currency": "USD",
            },
            fund_slug=fund_slug,
        )
        is_approved = event_type == AuditEventType.TRADE_APPROVED
        topic_base = "trades.approved" if is_approved else "trades.rejected"
        await self._event_bus.publish(fund_topic(fund_slug, topic_base), event)

    async def _audit_event(
        self,
        event_type: AuditEventType,
        *,
        actor_id: str,
        fund_slug: str,
        order: OrderRecord,
        extra: dict[str, object] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        if self._audit_repo is None:
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
        await self._audit_repo.insert_admin_event(
            event_type=event_type,
            actor_id=actor_id,
            actor_type="user",
            fund_slug=fund_slug,
            payload=payload,
            session=session,
        )

    @staticmethod
    def _to_summary(record: OrderRecord) -> OrderSummary:
        """Convert an OrderRecord to an OrderSummary."""
        from app.modules.orders.interface import AlgoType, OrderSide, OrderType, TimeInForce

        return OrderSummary(
            id=UUID(record.id),
            portfolio_id=UUID(record.portfolio_id),
            instrument_id=record.instrument_id,
            side=OrderSide(record.side),
            order_type=OrderType(record.order_type),
            quantity=record.quantity,
            filled_quantity=record.filled_quantity,
            limit_price=record.limit_price,
            avg_fill_price=record.avg_fill_price,
            state=OrderState(record.state),
            rejection_reason=record.rejection_reason,
            compliance_results=record.compliance_results,  # type: ignore[arg-type]
            time_in_force=TimeInForce(record.time_in_force),
            created_at=record.created_at,
            updated_at=record.updated_at,
            algo_type=AlgoType(record.algo_type) if record.algo_type else None,
            algo_params=record.algo_params,
            is_parent=record.is_parent,
            parent_order_id=UUID(record.parent_order_id) if record.parent_order_id else None,
            broker_id=record.broker_id,
        )
