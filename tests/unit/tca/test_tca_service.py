"""Unit tests for TCAService orchestration and VWAPCalculator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.tca.core.vwap import VWAPCalculator
from app.modules.tca.services.tca import TCAService

_ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
_PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_order(**overrides) -> MagicMock:
    o = MagicMock()
    o.id = str(_ORDER_ID)
    o.instrument_id = "AAPL"
    o.side = "buy"
    o.quantity = Decimal("1000")
    o.filled_quantity = Decimal("1000")
    o.avg_fill_price = Decimal("150.50")
    o.arrival_mid_price = Decimal("150.00")
    o.arrival_spread = Decimal("0.10")
    o.state = "filled"
    o.broker_id = None
    o.fund_slug = "alpha"
    o.portfolio_id = str(_PORTFOLIO_ID)
    o.updated_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    for k, v in overrides.items():
        setattr(o, k, v)
    return o


def _make_fill(filled_at: datetime) -> MagicMock:
    f = MagicMock()
    f.filled_at = filled_at
    return f


def _make_tca_service(
    *,
    order: MagicMock | None = None,
    fills: list | None = None,
    vwap: Decimal | None = Decimal("150.25"),
    tca_record: MagicMock | None = None,
) -> TCAService:
    order_repo = AsyncMock()
    tca_repo = AsyncMock()
    vwap_calc = AsyncMock(spec=VWAPCalculator)

    order_repo.get_by_id = AsyncMock(return_value=order)
    order_repo.get_fills = AsyncMock(return_value=fills or [])
    order_repo.get_by_portfolio = AsyncMock(return_value=[])
    def _save_with_computed_at(rec, **kw):
        rec.computed_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
        return rec
    tca_repo.save = AsyncMock(side_effect=_save_with_computed_at)
    tca_repo.get_by_order_id = AsyncMock(return_value=tca_record)
    tca_repo.get_by_order_ids = AsyncMock(return_value=[])
    vwap_calc.compute = AsyncMock(return_value=vwap)

    return TCAService(
        tca_repo=tca_repo,
        order_repo=order_repo,
        vwap_calculator=vwap_calc,
    )


class TestComputeForOrder:
    @pytest.mark.asyncio
    async def test_computes_tca_for_filled_order(self) -> None:
        order = _make_order()
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
            _make_fill(datetime(2026, 4, 10, 10, 30, 0, tzinfo=timezone.utc)),
        ]
        service = _make_tca_service(order=order, fills=fills)

        report = await service.compute_for_order(_ORDER_ID)

        assert report is not None
        assert report.order_id == _ORDER_ID
        assert report.instrument_id == "AAPL"
        assert report.total_cost_bps > Decimal("0")

    @pytest.mark.asyncio
    async def test_returns_none_when_order_not_found(self) -> None:
        service = _make_tca_service(order=None)
        assert await service.compute_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_filled(self) -> None:
        order = _make_order(state="pending")
        service = _make_tca_service(order=order)
        assert await service.compute_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_arrival_price(self) -> None:
        order = _make_order(arrival_mid_price=None)
        service = _make_tca_service(order=order)
        assert await service.compute_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_zero_arrival_price(self) -> None:
        order = _make_order(arrival_mid_price=Decimal("0"))
        service = _make_tca_service(order=order)
        assert await service.compute_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_fills(self) -> None:
        order = _make_order()
        service = _make_tca_service(order=order, fills=[])
        assert await service.compute_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_works_without_vwap(self) -> None:
        order = _make_order()
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
        ]
        service = _make_tca_service(order=order, fills=fills, vwap=None)

        report = await service.compute_for_order(_ORDER_ID)
        assert report is not None
        assert report.timing_cost_bps == Decimal("0")


class TestGetForOrder:
    @pytest.mark.asyncio
    async def test_returns_report_when_exists(self) -> None:
        order = _make_order()
        tca_record = MagicMock()
        tca_record.order_id = str(_ORDER_ID)
        tca_record.arrival_mid_price = Decimal("150.00")
        tca_record.arrival_spread = Decimal("0.10")
        tca_record.vwap_benchmark = Decimal("150.25")
        tca_record.total_cost_bps = Decimal("15.5000")
        tca_record.commission_cost_bps = Decimal("5")
        tca_record.spread_cost_bps = Decimal("3.3333")
        tca_record.market_impact_cost_bps = Decimal("5.0000")
        tca_record.timing_cost_bps = Decimal("2.1667")
        tca_record.opportunity_cost_bps = Decimal("0")
        tca_record.implementation_shortfall_bps = Decimal("15.5000")
        tca_record.participation_rate = None
        tca_record.execution_duration_seconds = 1800
        tca_record.total_cost_usd = Decimal("2325.00")
        tca_record.computed_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)

        service = _make_tca_service(order=order, tca_record=tca_record)
        report = await service.get_for_order(_ORDER_ID)

        assert report is not None
        assert report.total_cost_bps == Decimal("15.5000")

    @pytest.mark.asyncio
    async def test_returns_none_when_order_missing(self) -> None:
        service = _make_tca_service(order=None)
        assert await service.get_for_order(_ORDER_ID) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_tca_missing(self) -> None:
        order = _make_order()
        service = _make_tca_service(order=order, tca_record=None)
        assert await service.get_for_order(_ORDER_ID) is None


class TestVWAPCalculator:
    @pytest.mark.asyncio
    async def test_computes_vwap_with_volume(self) -> None:
        mds = AsyncMock()
        snap1 = MagicMock()
        snap1.mid = Decimal("100.00")
        snap1.volume = Decimal("5000")
        snap2 = MagicMock()
        snap2.mid = Decimal("101.00")
        snap2.volume = Decimal("3000")
        mds.get_price_history = AsyncMock(return_value=[snap1, snap2])

        calc = VWAPCalculator(mds)
        start = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)

        result = await calc.compute("AAPL", start, end)

        # VWAP = (100*5000 + 101*3000) / (5000 + 3000) = 803000/8000 = 100.375
        assert result is not None
        assert result == Decimal("100.37500000")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_snapshots(self) -> None:
        mds = AsyncMock()
        mds.get_price_history = AsyncMock(return_value=[])

        calc = VWAPCalculator(mds)
        start = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)

        assert await calc.compute("AAPL", start, end) is None

    @pytest.mark.asyncio
    async def test_falls_back_to_simple_avg_with_zero_volume(self) -> None:
        mds = AsyncMock()
        snap1 = MagicMock()
        snap1.mid = Decimal("100.00")
        snap1.volume = Decimal("0")
        snap2 = MagicMock()
        snap2.mid = Decimal("102.00")
        snap2.volume = None
        mds.get_price_history = AsyncMock(return_value=[snap1, snap2])

        calc = VWAPCalculator(mds)
        start = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)

        result = await calc.compute("AAPL", start, end)
        # Simple average = (100 + 102) / 2 = 101
        assert result == Decimal("101")

    @pytest.mark.asyncio
    async def test_returns_none_when_all_mids_zero(self) -> None:
        mds = AsyncMock()
        snap = MagicMock()
        snap.mid = Decimal("0")
        snap.volume = Decimal("0")
        mds.get_price_history = AsyncMock(return_value=[snap])

        calc = VWAPCalculator(mds)
        start = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)

        assert await calc.compute("AAPL", start, end) is None
