"""Unit tests for PositionReconciler — three-way position + cash reconciliation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.eod.core.reconciler import PositionReconciler
from app.modules.eod.interfaces.reconciliation import BreakType

_PID = uuid4()
_DATE = date(2026, 4, 10)
ZERO = Decimal(0)


def _make_position(instrument_id: str, quantity: Decimal) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    return p


def _make_balance(currency: str, total_balance: Decimal) -> MagicMock:
    b = MagicMock()
    b.currency = currency
    b.total_balance = total_balance
    return b


def _make_service(
    internal_positions: list | None = None,
    broker_map: dict[str, Decimal] | None = None,
    admin_map: dict[str, Decimal] | None = None,
    internal_cash: list | None = None,
    admin_cash: dict[str, Decimal] | None = None,
    with_break_repo: bool = False,
    with_auto_resolver: bool = False,
) -> PositionReconciler:
    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=internal_positions or [])

    broker_adapter = AsyncMock()
    broker_adapter.get_eod_positions = AsyncMock(return_value=broker_map or {})

    recon_repo = AsyncMock()
    recon_repo.upsert = AsyncMock()

    break_repo = AsyncMock() if with_break_repo else None
    if break_repo:
        break_repo.create_many = AsyncMock()

    fund_admin_adapter = None
    if admin_map is not None:
        fund_admin_adapter = AsyncMock()
        fund_admin_adapter.get_positions = AsyncMock(return_value=admin_map)
        fund_admin_adapter.get_cash_balances = AsyncMock(return_value=admin_cash or {})

    cash_service = None
    if internal_cash is not None:
        cash_service = AsyncMock()
        cash_service.get_balances = AsyncMock(return_value=internal_cash)

    auto_resolver = None
    if with_auto_resolver and break_repo:
        auto_resolver = AsyncMock()
        auto_resolver.process_breaks = AsyncMock(
            return_value=MagicMock(auto_resolved=0, auto_escalated=0)
        )

    return PositionReconciler(
        position_service=position_service,
        broker_adapter=broker_adapter,
        recon_repo=recon_repo,
        break_repo=break_repo,
        fund_admin_adapter=fund_admin_adapter,
        cash_service=cash_service,
        auto_resolver=auto_resolver,
    )


class TestTwoWayReconciliation:
    @pytest.mark.asyncio
    async def test_clean_recon(self) -> None:
        """Internal and broker agree on everything."""
        positions = [_make_position("AAPL", Decimal("100")), _make_position("MSFT", Decimal("50"))]
        broker = {"AAPL": Decimal("100"), "MSFT": Decimal("50")}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        assert result.is_clean
        assert result.total_positions == 2
        assert result.matched_positions == 2
        assert result.breaks == []

    @pytest.mark.asyncio
    async def test_quantity_mismatch(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("95")}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        assert not result.is_clean
        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.QUANTITY_MISMATCH
        assert result.breaks[0].difference == Decimal("5")

    @pytest.mark.asyncio
    async def test_missing_internal(self) -> None:
        """Broker has a position we don't have internally."""
        positions = []
        broker = {"AAPL": Decimal("100")}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.MISSING_INTERNAL

    @pytest.mark.asyncio
    async def test_missing_broker(self) -> None:
        """We have a position the broker doesn't."""
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.MISSING_BROKER

    @pytest.mark.asyncio
    async def test_materiality_threshold(self) -> None:
        """A difference of 0.005 is below MATERIAL_THRESHOLD=0.01."""
        positions = [_make_position("AAPL", Decimal("100.005"))]
        broker = {"AAPL": Decimal("100")}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        # Still a QUANTITY_MISMATCH break, but not material
        assert len(result.breaks) == 1
        assert result.breaks[0].is_material is False


class TestThreeWayReconciliation:
    @pytest.mark.asyncio
    async def test_all_three_agree(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("100")}
        admin = {"AAPL": Decimal("100")}
        svc = _make_service(internal_positions=positions, broker_map=broker, admin_map=admin)

        result = await svc.reconcile(_PID, _DATE)

        assert result.is_clean
        assert result.breaks == []

    @pytest.mark.asyncio
    async def test_missing_admin(self) -> None:
        """Internal and broker agree, admin has zero."""
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("100")}
        admin = {"AAPL": ZERO}
        svc = _make_service(internal_positions=positions, broker_map=broker, admin_map=admin)

        result = await svc.reconcile(_PID, _DATE)

        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.MISSING_ADMIN

    @pytest.mark.asyncio
    async def test_internal_admin_mismatch(self) -> None:
        """Internal and broker agree, but admin differs."""
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("100")}
        admin = {"AAPL": Decimal("95")}
        svc = _make_service(internal_positions=positions, broker_map=broker, admin_map=admin)

        result = await svc.reconcile(_PID, _DATE)

        types = {b.break_type for b in result.breaks}
        assert BreakType.INTERNAL_ADMIN_MISMATCH in types

    @pytest.mark.asyncio
    async def test_admin_positions_unavailable(self) -> None:
        """Admin adapter throws — should fall back to two-way."""
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("100")}
        svc = _make_service(internal_positions=positions, broker_map=broker)
        # Manually set up admin adapter that throws
        svc._admin = AsyncMock()
        svc._admin.get_positions = AsyncMock(side_effect=RuntimeError("down"))
        svc._admin.get_cash_balances = AsyncMock(return_value={})

        result = await svc.reconcile(_PID, _DATE)

        # Falls back to two-way — internal and broker agree, so clean
        assert result.is_clean


class TestCashReconciliation:
    @pytest.mark.asyncio
    async def test_cash_break(self) -> None:
        """Cash mismatch between internal and admin."""
        positions = []
        broker: dict[str, Decimal] = {}
        admin: dict[str, Decimal] = {}
        internal_cash = [_make_balance("USD", Decimal("100000"))]
        admin_cash = {"USD": Decimal("99000")}
        svc = _make_service(
            internal_positions=positions,
            broker_map=broker,
            admin_map=admin,
            internal_cash=internal_cash,
            admin_cash=admin_cash,
        )

        result = await svc.reconcile(_PID, _DATE)

        assert len(result.cash_breaks) == 1
        assert result.cash_breaks[0].currency == "USD"
        assert result.cash_breaks[0].difference == Decimal("1000")
        assert not result.is_clean

    @pytest.mark.asyncio
    async def test_cash_within_threshold(self) -> None:
        """Cash difference of 0.50 is below CASH_MATERIAL_THRESHOLD=1.00."""
        positions = []
        broker: dict[str, Decimal] = {}
        admin: dict[str, Decimal] = {}
        internal_cash = [_make_balance("USD", Decimal("100000.50"))]
        admin_cash = {"USD": Decimal("100000")}
        svc = _make_service(
            internal_positions=positions,
            broker_map=broker,
            admin_map=admin,
            internal_cash=internal_cash,
            admin_cash=admin_cash,
        )

        result = await svc.reconcile(_PID, _DATE)

        assert result.cash_breaks == []

    @pytest.mark.asyncio
    async def test_no_cash_service_skips(self) -> None:
        """Without cash service, no cash reconciliation happens."""
        positions = []
        broker: dict[str, Decimal] = {}
        svc = _make_service(internal_positions=positions, broker_map=broker)

        result = await svc.reconcile(_PID, _DATE)

        assert result.cash_breaks == []


class TestPersistAndAutoResolve:
    @pytest.mark.asyncio
    async def test_persists_breaks(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("90")}
        svc = _make_service(
            internal_positions=positions, broker_map=broker, with_break_repo=True,
        )

        await svc.reconcile(_PID, _DATE)

        svc._break_repo.create_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_resolver_called(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("90")}
        svc = _make_service(
            internal_positions=positions,
            broker_map=broker,
            with_break_repo=True,
            with_auto_resolver=True,
        )

        await svc.reconcile(_PID, _DATE)

        svc._auto_resolver.process_breaks.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_breaks_no_persist(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"))]
        broker = {"AAPL": Decimal("100")}
        svc = _make_service(
            internal_positions=positions, broker_map=broker, with_break_repo=True,
        )

        await svc.reconcile(_PID, _DATE)

        svc._break_repo.create_many.assert_not_called()
