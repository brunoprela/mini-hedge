"""Unit tests for AllocationService — block trade allocation lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.orders.interfaces import (
    AllocationState,
    OrderSide,
    OrderState,
    OrderType,
)
from app.modules.orders.interfaces.allocation import (
    AllocationLegRequest,
    CreateBlockAllocationRequest,
)
from app.modules.orders.services.allocation import AllocationService

ZERO = Decimal(0)
_PID = uuid4()


def _make_allocation_record(
    allocation_id: str | None = None,
    state: str = AllocationState.DRAFT.value,
    side: str = "buy",
    execution_order_id: str | None = None,
    execution_fund_slug: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = allocation_id or str(uuid4())
    r.instrument_id = "AAPL"
    r.side = side
    r.total_quantity = Decimal("1000")
    r.filled_quantity = ZERO
    r.avg_fill_price = None
    r.state = state
    r.order_type = "market"
    r.limit_price = None
    r.algo_type = None
    r.algo_params = None
    r.created_by = "user-1"
    r.created_at = datetime.now(timezone.utc)
    r.execution_order_id = execution_order_id
    r.execution_fund_slug = execution_fund_slug
    return r


def _make_leg_record(
    leg_id: str | None = None,
    fund_slug: str = "alpha",
    target_pct: Decimal = Decimal("0.5"),
    target_quantity: Decimal = Decimal("500"),
    state: str = AllocationState.APPROVED.value,
) -> MagicMock:
    r = MagicMock()
    r.id = leg_id or str(uuid4())
    r.block_allocation_id = str(uuid4())
    r.fund_slug = fund_slug
    r.portfolio_id = str(_PID)
    r.target_pct = target_pct
    r.target_quantity = target_quantity
    r.filled_quantity = ZERO
    r.avg_fill_price = None
    r.state = state
    r.compliance_results = None
    return r


def _make_order_summary(
    state: str = OrderState.SENT.value,
    filled_quantity: Decimal = ZERO,
) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.state = state
    s.filled_quantity = filled_quantity
    s.avg_fill_price = None
    return s


def _make_compliance_decision(approved: bool = True) -> MagicMock:
    d = MagicMock()
    d.approved = approved
    d.results = []
    d.blocked_by = []
    return d


def _make_service(
    allocation: MagicMock | None = None,
    legs: list | None = None,
    compliance_approved: bool = True,
    order_summary: MagicMock | None = None,
) -> AllocationService:
    session_factory = MagicMock()
    # fund_scope returns an async context manager
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock()
    cm.__aexit__ = AsyncMock(return_value=False)
    session_factory.fund_scope = MagicMock(return_value=cm)

    allocation_repo = AsyncMock()

    def _save_alloc(record, **kw):
        if not isinstance(record.id, str):
            record.id = str(uuid4())
        return record

    def _save_leg(record, **kw):
        if not isinstance(record.id, str):
            record.id = str(uuid4())
        return record

    allocation_repo.save_allocation = AsyncMock(side_effect=_save_alloc)
    allocation_repo.save_leg = AsyncMock(side_effect=_save_leg)
    allocation_repo.update_allocation_state = AsyncMock()
    allocation_repo.update_leg = AsyncMock()
    allocation_repo.get_allocation_by_id = AsyncMock(return_value=allocation)
    allocation_repo.get_legs = AsyncMock(return_value=legs or [])

    order_service = AsyncMock()
    order_service.create_order = AsyncMock(
        return_value=order_summary or _make_order_summary()
    )
    order_service.create_algo_order = AsyncMock(
        return_value=order_summary or _make_order_summary()
    )
    order_service.cancel_order = AsyncMock()

    order_repo = AsyncMock()
    order_repo.get_by_id = AsyncMock(return_value=None)

    compliance_gateway = AsyncMock()
    compliance_gateway.check = AsyncMock(
        return_value=_make_compliance_decision(compliance_approved)
    )

    event_bus = AsyncMock()

    return AllocationService(
        session_factory=session_factory,
        allocation_repo=allocation_repo,
        order_service=order_service,
        order_repo=order_repo,
        compliance_gateway=compliance_gateway,
        event_bus=event_bus,
    )


class TestGetAllocation:
    @pytest.mark.asyncio
    async def test_returns_summary(self) -> None:
        alloc = _make_allocation_record()
        legs = [_make_leg_record()]
        svc = _make_service(allocation=alloc, legs=legs)

        result = await svc.get_allocation(UUID(alloc.id))

        assert result.instrument_id == "AAPL"
        assert len(result.legs) == 1

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc = _make_service(allocation=None)

        with pytest.raises(LookupError, match="not found"):
            await svc.get_allocation(uuid4())


class TestCreateBlockAllocation:
    @pytest.mark.asyncio
    async def test_validates_legs_sum_to_100pct(self) -> None:
        svc = _make_service()
        request = CreateBlockAllocationRequest(
            instrument_id="AAPL",
            side=OrderSide.BUY,
            total_quantity=Decimal("1000"),
            legs=[
                AllocationLegRequest(fund_slug="alpha", portfolio_id=_PID, target_pct=Decimal("0.3")),
                AllocationLegRequest(fund_slug="beta", portfolio_id=_PID, target_pct=Decimal("0.3")),
            ],
        )

        with pytest.raises(ValueError, match="sum to 100%"):
            await svc.create_block_allocation(request, "user-1")

    @pytest.mark.asyncio
    async def test_validates_empty_legs(self) -> None:
        svc = _make_service()
        request = CreateBlockAllocationRequest(
            instrument_id="AAPL",
            side=OrderSide.BUY,
            total_quantity=Decimal("1000"),
            legs=[],
        )

        with pytest.raises(ValueError, match="sum to 100%"):
            await svc.create_block_allocation(request, "user-1")

    @pytest.mark.asyncio
    async def test_creates_approved_allocation(self) -> None:
        alloc = _make_allocation_record(state=AllocationState.EXECUTING.value)
        legs = [_make_leg_record(fund_slug="alpha", target_pct=Decimal("1.0"), target_quantity=Decimal("1000"))]
        svc = _make_service(allocation=alloc, legs=legs, compliance_approved=True)

        request = CreateBlockAllocationRequest(
            instrument_id="AAPL",
            side=OrderSide.BUY,
            total_quantity=Decimal("1000"),
            legs=[
                AllocationLegRequest(fund_slug="alpha", portfolio_id=_PID, target_pct=Decimal("1.0")),
            ],
        )

        result = await svc.create_block_allocation(request, "user-1")

        # Compliance was checked
        svc._compliance_gateway.check.assert_called_once()
        # Execution order was created
        svc._order_service.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejected_allocation(self) -> None:
        alloc = _make_allocation_record(state=AllocationState.REJECTED.value)
        legs = [_make_leg_record(state=AllocationState.REJECTED.value)]
        svc = _make_service(allocation=alloc, legs=legs, compliance_approved=False)

        request = CreateBlockAllocationRequest(
            instrument_id="AAPL",
            side=OrderSide.BUY,
            total_quantity=Decimal("1000"),
            legs=[
                AllocationLegRequest(fund_slug="alpha", portfolio_id=_PID, target_pct=Decimal("1.0")),
            ],
        )

        result = await svc.create_block_allocation(request, "user-1")

        # No execution order should have been created
        svc._order_service.create_order.assert_not_called()


class TestAllocateFills:
    @pytest.mark.asyncio
    async def test_distributes_fills_prorata(self) -> None:
        exec_oid = str(uuid4())
        alloc = _make_allocation_record(
            state=AllocationState.EXECUTING.value,
            execution_order_id=exec_oid,
            execution_fund_slug="alpha",
        )
        legs = [
            _make_leg_record(fund_slug="alpha", target_pct=Decimal("0.6")),
            _make_leg_record(fund_slug="beta", target_pct=Decimal("0.4")),
        ]
        exec_order = MagicMock()
        exec_order.filled_quantity = Decimal("500")
        exec_order.avg_fill_price = Decimal("150")

        svc = _make_service(allocation=alloc, legs=legs)
        svc._order_repo.get_by_id = AsyncMock(return_value=exec_order)

        await svc.allocate_fills(UUID(alloc.id))

        # Legs should be updated with fills
        assert svc._allocation_repo.update_leg.call_count == 2
        # Events should be published for each leg
        assert svc._event_bus.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_no_allocation_is_noop(self) -> None:
        svc = _make_service(allocation=None)

        await svc.allocate_fills(uuid4())

        svc._allocation_repo.update_leg.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_execution_order_is_noop(self) -> None:
        alloc = _make_allocation_record(execution_order_id=None)
        svc = _make_service(allocation=alloc)

        await svc.allocate_fills(UUID(alloc.id))

        svc._allocation_repo.update_leg.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_fills_is_noop(self) -> None:
        alloc = _make_allocation_record(
            execution_order_id=str(uuid4()),
            execution_fund_slug="alpha",
        )
        exec_order = MagicMock()
        exec_order.filled_quantity = ZERO

        svc = _make_service(allocation=alloc)
        svc._order_repo.get_by_id = AsyncMock(return_value=exec_order)

        await svc.allocate_fills(UUID(alloc.id))

        svc._allocation_repo.update_leg.assert_not_called()


class TestCancelAllocation:
    @pytest.mark.asyncio
    async def test_cancels_allocation(self) -> None:
        alloc = _make_allocation_record(
            state=AllocationState.EXECUTING.value,
            execution_order_id=str(uuid4()),
            execution_fund_slug="alpha",
        )
        legs = [_make_leg_record(state=AllocationState.APPROVED.value)]
        svc = _make_service(allocation=alloc, legs=legs)

        result = await svc.cancel_allocation(UUID(alloc.id), "user-1")

        svc._order_service.cancel_order.assert_called_once()
        svc._allocation_repo.update_allocation_state.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_not_found(self) -> None:
        svc = _make_service(allocation=None)

        with pytest.raises(LookupError, match="not found"):
            await svc.cancel_allocation(uuid4(), "user-1")

    @pytest.mark.asyncio
    async def test_cancel_terminal_state_raises(self) -> None:
        alloc = _make_allocation_record(state=AllocationState.ALLOCATED.value)
        svc = _make_service(allocation=alloc)

        with pytest.raises(ValueError, match="Cannot cancel"):
            await svc.cancel_allocation(UUID(alloc.id), "user-1")
