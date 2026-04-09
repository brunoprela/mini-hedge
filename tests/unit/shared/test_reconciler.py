"""Unit tests for the EOD position reconciler."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.eod.core.reconciler import PositionReconciler
from app.modules.eod.interfaces.reconciliation import BreakType


def _mock_position(iid: str, qty: Decimal):
    pos = MagicMock()
    pos.instrument_id = iid
    pos.quantity = qty
    return pos


@pytest.fixture
def position_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def broker_adapter() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def recon_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def reconciler(position_service, broker_adapter, recon_repo) -> PositionReconciler:
    return PositionReconciler(
        position_service=position_service,
        broker_adapter=broker_adapter,
        recon_repo=recon_repo,
    )


PORTFOLIO_ID = uuid4()
BIZ_DATE = date(2024, 1, 15)


class TestCleanReconciliation:
    async def test_matching_positions(self, reconciler, position_service, broker_adapter):
        position_service.get_by_portfolio.return_value = [
            _mock_position("AAPL", Decimal("100")),
            _mock_position("TSLA", Decimal("50")),
        ]
        broker_adapter.get_eod_positions.return_value = {
            "AAPL": Decimal("100"),
            "TSLA": Decimal("50"),
        }

        result = await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        assert result.is_clean is True
        assert len(result.breaks) == 0
        assert result.total_positions == 2
        assert result.matched_positions == 2


class TestQuantityMismatch:
    async def test_detects_quantity_difference(self, reconciler, position_service, broker_adapter):
        position_service.get_by_portfolio.return_value = [
            _mock_position("AAPL", Decimal("100")),
        ]
        broker_adapter.get_eod_positions.return_value = {
            "AAPL": Decimal("95"),
        }

        result = await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        assert result.is_clean is False
        assert len(result.breaks) == 1
        brk = result.breaks[0]
        assert brk.break_type == BreakType.QUANTITY_MISMATCH
        assert brk.instrument_id == "AAPL"
        assert brk.internal_quantity == Decimal("100")
        assert brk.broker_quantity == Decimal("95")
        assert brk.difference == Decimal("5")


class TestMissingPositions:
    async def test_missing_at_broker(self, reconciler, position_service, broker_adapter):
        position_service.get_by_portfolio.return_value = [
            _mock_position("AAPL", Decimal("100")),
        ]
        broker_adapter.get_eod_positions.return_value = {}

        result = await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        assert result.is_clean is False
        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.MISSING_BROKER

    async def test_missing_internally(self, reconciler, position_service, broker_adapter):
        position_service.get_by_portfolio.return_value = []
        broker_adapter.get_eod_positions.return_value = {
            "AAPL": Decimal("100"),
        }

        result = await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        assert result.is_clean is False
        assert len(result.breaks) == 1
        assert result.breaks[0].break_type == BreakType.MISSING_INTERNAL


class TestMateriality:
    async def test_immaterial_difference_still_a_break(
        self, reconciler, position_service, broker_adapter
    ):
        """Even sub-threshold differences are still reported as breaks."""
        position_service.get_by_portfolio.return_value = [
            _mock_position("AAPL", Decimal("100.005")),
        ]
        broker_adapter.get_eod_positions.return_value = {
            "AAPL": Decimal("100.000"),
        }

        result = await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        assert len(result.breaks) == 1
        assert result.breaks[0].is_material is False


class TestPersistence:
    async def test_result_persisted(self, reconciler, position_service, broker_adapter, recon_repo):
        position_service.get_by_portfolio.return_value = [
            _mock_position("AAPL", Decimal("100")),
        ]
        broker_adapter.get_eod_positions.return_value = {
            "AAPL": Decimal("100"),
        }

        await reconciler.reconcile(PORTFOLIO_ID, BIZ_DATE)
        recon_repo.upsert.assert_called_once()
        call_kwargs = recon_repo.upsert.call_args.kwargs
        assert call_kwargs["is_clean"] is True
        assert call_kwargs["total_positions"] == 1
