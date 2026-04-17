"""Block trade allocation service — cross-fund fill distribution."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.orders.interfaces import (
    AlgoParams,
    AlgoType,
    AllocationLegSummary,
    AllocationState,
    BlockAllocationSummary,
    CreateAlgoOrderRequest,
    CreateBlockAllocationRequest,
    CreateOrderRequest,
    OrderState,
)
from app.modules.orders.models import (
    AllocationLegRecord,
    BlockAllocationRecord,
)
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.modules.orders.core.compliance_gateway import ComplianceGateway
    from app.modules.orders.repositories import AllocationRepository, OrderRepository
    from app.modules.orders.services.order import OrderService
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)


class AllocationService:
    """Manages block trade allocation lifecycle — compliance, execution, distribution."""

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        allocation_repo: AllocationRepository,
        order_service: OrderService,
        order_repo: OrderRepository,
        compliance_gateway: ComplianceGateway,
        event_bus: EventBus | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._allocation_repo = allocation_repo
        self._order_service = order_service
        self._order_repo = order_repo
        self._compliance_gateway = compliance_gateway
        self._event_bus = event_bus

    async def create_block_allocation(
        self,
        request: CreateBlockAllocationRequest,
        actor_id: str,
    ) -> BlockAllocationSummary:
        """Create a block allocation, compliance-check each leg, then execute."""
        # Validate legs sum to 100%
        total_pct = sum(leg.target_pct for leg in request.legs)
        if abs(total_pct - Decimal(1)) > Decimal("0.0001"):
            msg = f"Allocation legs must sum to 100%, got {total_pct}"
            raise ValueError(msg)

        if not request.legs:
            msg = "At least one allocation leg is required"
            raise ValueError(msg)

        # Create the block allocation record
        allocation_id = str(uuid4())
        allocation = BlockAllocationRecord(
            id=allocation_id,
            instrument_id=request.instrument_id,
            side=request.side.value,
            total_quantity=request.total_quantity,
            filled_quantity=ZERO,
            state=AllocationState.DRAFT.value,
            order_type=request.order_type.value,
            limit_price=request.limit_price,
            algo_type=request.algo_type.value if request.algo_type else None,
            algo_params=request.algo_params.model_dump() if request.algo_params else None,
            created_by=actor_id,
        )
        allocation = await self._allocation_repo.insert_allocation(allocation)

        # Create legs with target quantities
        legs: list[AllocationLegRecord] = []
        allocated_qty = ZERO
        for i, leg_req in enumerate(request.legs):
            if i == len(request.legs) - 1:
                # Last leg gets remainder to avoid rounding issues
                target_qty = request.total_quantity - allocated_qty
            else:
                target_qty = (request.total_quantity * leg_req.target_pct).quantize(
                    Decimal("0.00000001")
                )
            allocated_qty += target_qty

            leg = AllocationLegRecord(
                id=str(uuid4()),
                block_allocation_id=allocation_id,
                fund_slug=leg_req.fund_slug,
                portfolio_id=str(leg_req.portfolio_id),
                target_pct=leg_req.target_pct,
                target_quantity=target_qty,
                filled_quantity=ZERO,
                state=AllocationState.PENDING_COMPLIANCE.value,
            )
            leg = await self._allocation_repo.insert_leg(leg)
            legs.append(leg)

        # Compliance check per leg (per fund/portfolio)
        await self._allocation_repo.update_allocation_state(
            UUID(allocation_id), AllocationState.PENDING_COMPLIANCE.value
        )

        all_approved = True
        for leg in legs:
            from app.modules.compliance.interfaces import TradeCheckRequest

            check = TradeCheckRequest(
                portfolio_id=UUID(leg.portfolio_id),
                instrument_id=request.instrument_id,
                side=request.side.value,
                quantity=leg.target_quantity,
                price=request.limit_price or Decimal("100.00"),
            )
            decision = await self._compliance_gateway.check(check)
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

            if decision.approved:
                await self._allocation_repo.update_leg(
                    UUID(leg.id),
                    state=AllocationState.APPROVED.value,
                    compliance_results=compliance_data,
                )
            else:
                all_approved = False
                await self._allocation_repo.update_leg(
                    UUID(leg.id),
                    state=AllocationState.REJECTED.value,
                    compliance_results=compliance_data,
                )

        if not all_approved:
            await self._allocation_repo.update_allocation_state(
                UUID(allocation_id), AllocationState.REJECTED.value
            )
            logger.info("block_allocation_rejected", allocation_id=allocation_id)
            return await self.get_allocation(UUID(allocation_id))

        # All legs approved — pick execution fund and create execution order
        await self._allocation_repo.update_allocation_state(
            UUID(allocation_id), AllocationState.APPROVED.value
        )

        # Execute in the first leg's fund (or the largest allocation)
        execution_leg = max(legs, key=lambda leg: leg.target_quantity)
        execution_fund = execution_leg.fund_slug

        # Create the execution order in the execution fund's schema
        async with self._session_factory.fund_scope(execution_fund):
            if request.algo_type is not None:
                algo_request = CreateAlgoOrderRequest(
                    portfolio_id=UUID(execution_leg.portfolio_id),
                    instrument_id=request.instrument_id,
                    side=request.side,
                    order_type=request.order_type,
                    quantity=request.total_quantity,
                    limit_price=request.limit_price,
                    algo_type=request.algo_type,
                    algo_params=request.algo_params or AlgoParams(),
                )
                order_summary = await self._order_service.create_algo_order(
                    algo_request, execution_fund, actor_id
                )
            else:
                order_request = CreateOrderRequest(
                    portfolio_id=UUID(execution_leg.portfolio_id),
                    instrument_id=request.instrument_id,
                    side=request.side,
                    order_type=request.order_type,
                    quantity=request.total_quantity,
                    limit_price=request.limit_price,
                )
                order_summary = await self._order_service.create_order(
                    order_request, execution_fund, actor_id
                )

        await self._allocation_repo.update_allocation_state(
            UUID(allocation_id),
            AllocationState.EXECUTING.value,
            execution_fund_slug=execution_fund,
            execution_order_id=str(order_summary.id),
        )

        logger.info(
            "block_allocation_executing",
            allocation_id=allocation_id,
            execution_fund=execution_fund,
            execution_order_id=str(order_summary.id),
        )

        # If the order was immediately filled (sync broker), allocate now
        if order_summary.state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
            await self.allocate_fills(UUID(allocation_id))

        return await self.get_allocation(UUID(allocation_id))

    async def allocate_fills(self, allocation_id: UUID) -> None:
        """Distribute fills from the execution order across allocation legs pro-rata."""
        allocation = await self._allocation_repo.get_allocation_by_id(allocation_id)
        if allocation is None:
            return

        if allocation.execution_order_id is None:
            return

        # Get execution order fills
        execution_fund = allocation.execution_fund_slug
        if execution_fund is None:
            return
        async with self._session_factory.fund_scope(execution_fund):
            exec_order = await self._order_repo.get_by_id(UUID(allocation.execution_order_id))

        if exec_order is None or exec_order.filled_quantity <= ZERO:
            return

        total_filled = exec_order.filled_quantity
        avg_price = exec_order.avg_fill_price or ZERO

        legs = await self._allocation_repo.get_legs(allocation_id)

        # Pro-rata distribution with rounding residual to largest leg
        allocated = ZERO
        leg_fills: list[tuple[AllocationLegRecord, Decimal]] = []

        for i, leg in enumerate(legs):
            if i == len(legs) - 1:
                # Last leg gets remainder to absorb rounding residual
                qty = total_filled - allocated
            else:
                qty = (total_filled * leg.target_pct).quantize(Decimal("0.00000001"))
            allocated += qty
            leg_fills.append((leg, qty))

        # Publish trades for each leg's fund
        for leg, fill_qty in leg_fills:
            if fill_qty <= ZERO:
                continue

            await self._allocation_repo.update_leg(
                UUID(leg.id),
                filled_quantity=fill_qty,
                avg_fill_price=avg_price,
                state=AllocationState.ALLOCATED.value,
            )

            # Publish trade event in the leg's fund
            event = BaseEvent(
                event_type=(
                    AuditEventType.TRADE_BUY
                    if allocation.side == "buy"
                    else AuditEventType.TRADE_SELL
                ),
                data={
                    "portfolio_id": leg.portfolio_id,
                    "instrument_id": allocation.instrument_id,
                    "side": allocation.side,
                    "quantity": str(fill_qty),
                    "price": str(avg_price),
                    "trade_id": str(uuid4()),
                    "currency": "USD",
                    "block_allocation_id": str(allocation_id),
                },
                fund_slug=leg.fund_slug,
            )
            if self._event_bus:
                await self._event_bus.publish(fund_topic(leg.fund_slug, "trades.executed"), event)

        # Update allocation as fully allocated
        await self._allocation_repo.update_allocation_state(
            allocation_id,
            AllocationState.ALLOCATED.value,
            filled_quantity=total_filled,
            avg_fill_price=avg_price,
        )

        logger.info(
            "block_allocation_allocated",
            allocation_id=str(allocation_id),
            total_filled=str(total_filled),
            avg_price=str(avg_price),
            legs=len(legs),
        )

    async def get_allocation(self, allocation_id: UUID) -> BlockAllocationSummary:
        """Get a block allocation with its legs."""
        allocation = await self._allocation_repo.get_allocation_by_id(allocation_id)
        if allocation is None:
            msg = f"Allocation {allocation_id} not found"
            raise LookupError(msg)

        legs = await self._allocation_repo.get_legs(allocation_id)
        return self._to_summary(allocation, legs)

    async def cancel_allocation(self, allocation_id: UUID, actor_id: str) -> BlockAllocationSummary:
        """Cancel a block allocation and its execution order if active."""
        allocation = await self._allocation_repo.get_allocation_by_id(allocation_id)
        if allocation is None:
            msg = f"Allocation {allocation_id} not found"
            raise LookupError(msg)

        terminal = {AllocationState.ALLOCATED, AllocationState.CANCELLED, AllocationState.REJECTED}
        if AllocationState(allocation.state) in terminal:
            msg = f"Cannot cancel allocation in state {allocation.state}"
            raise ValueError(msg)

        # Cancel the execution order if one exists
        if allocation.execution_order_id and allocation.execution_fund_slug:
            try:
                async with self._session_factory.fund_scope(allocation.execution_fund_slug):
                    await self._order_service.cancel_order(
                        UUID(allocation.execution_order_id), actor_id=actor_id
                    )
            except Exception:
                logger.warning(
                    "allocation_exec_order_cancel_failed",
                    allocation_id=str(allocation_id),
                    order_id=allocation.execution_order_id,
                )

        # Cancel all legs
        legs = await self._allocation_repo.get_legs(allocation_id)
        for leg in legs:
            if leg.state not in (AllocationState.ALLOCATED, AllocationState.CANCELLED):
                await self._allocation_repo.update_leg(
                    UUID(leg.id), state=AllocationState.CANCELLED.value
                )

        await self._allocation_repo.update_allocation_state(
            allocation_id, AllocationState.CANCELLED.value
        )
        logger.info("block_allocation_cancelled", allocation_id=str(allocation_id))
        return await self.get_allocation(allocation_id)

    @staticmethod
    def _to_summary(
        record: BlockAllocationRecord,
        legs: list[AllocationLegRecord],
    ) -> BlockAllocationSummary:
        return BlockAllocationSummary(
            id=UUID(record.id),
            instrument_id=record.instrument_id,
            side=record.side,
            total_quantity=record.total_quantity,
            filled_quantity=record.filled_quantity,
            avg_fill_price=record.avg_fill_price,
            state=AllocationState(record.state),
            algo_type=AlgoType(record.algo_type) if record.algo_type else None,
            legs=[
                AllocationLegSummary(
                    id=UUID(leg.id),
                    fund_slug=leg.fund_slug,
                    portfolio_id=UUID(leg.portfolio_id),
                    target_pct=leg.target_pct,
                    target_quantity=leg.target_quantity,
                    filled_quantity=leg.filled_quantity,
                    avg_fill_price=leg.avg_fill_price,
                    state=leg.state,
                )
                for leg in legs
            ],
            created_by=record.created_by,
            created_at=record.created_at,
        )
