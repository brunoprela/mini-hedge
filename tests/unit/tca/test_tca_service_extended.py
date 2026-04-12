"""Extended TCA service tests — covers event publishing, scorecard lookup,
portfolio reports, and fund summary."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.tca.core.vwap import VWAPCalculator
from app.modules.tca.services.tca import TCAService

_ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
_PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000002")
_ZERO = Decimal("0")


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


def _make_tca_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.order_id = str(_ORDER_ID)
    r.arrival_mid_price = Decimal("150.00")
    r.arrival_spread = Decimal("0.10")
    r.vwap_benchmark = Decimal("150.25")
    r.total_cost_bps = Decimal("15.5000")
    r.commission_cost_bps = Decimal("5.0000")
    r.spread_cost_bps = Decimal("3.3333")
    r.market_impact_cost_bps = Decimal("5.0000")
    r.timing_cost_bps = Decimal("2.1667")
    r.opportunity_cost_bps = Decimal("0")
    r.implementation_shortfall_bps = Decimal("15.5000")
    r.participation_rate = None
    r.execution_duration_seconds = 1800
    r.total_cost_usd = Decimal("2325.00")
    r.computed_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_service(
    *,
    order: MagicMock | None = None,
    fills: list | None = None,
    vwap: Decimal | None = Decimal("150.25"),
    tca_record: MagicMock | None = None,
    scorecard_service: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
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
        scorecard_service=scorecard_service,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# Scorecard branch (lines 93-96)
# ---------------------------------------------------------------------------


class TestComputeWithScorecard:
    @pytest.mark.asyncio
    async def test_uses_scorecard_commission_when_available(self) -> None:
        order = _make_order(broker_id="broker-1")
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
            _make_fill(datetime(2026, 4, 10, 10, 30, 0, tzinfo=timezone.utc)),
        ]
        scorecard_svc = AsyncMock()
        scorecard = MagicMock()
        scorecard.avg_cost_bps = Decimal("8")
        scorecard_svc.get_scorecard = AsyncMock(return_value=scorecard)

        service = _make_service(
            order=order,
            fills=fills,
            scorecard_service=scorecard_svc,
        )
        report = await service.compute_for_order(_ORDER_ID)

        assert report is not None
        # Commission should be 8 bps from scorecard, not default 5
        assert report.commission_cost_bps == Decimal("8.0000")
        scorecard_svc.get_scorecard.assert_awaited_once_with("broker-1", "alpha")

    @pytest.mark.asyncio
    async def test_falls_back_to_default_when_scorecard_zero(self) -> None:
        order = _make_order(broker_id="broker-1")
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
        ]
        scorecard_svc = AsyncMock()
        scorecard = MagicMock()
        scorecard.avg_cost_bps = Decimal("0")
        scorecard_svc.get_scorecard = AsyncMock(return_value=scorecard)

        service = _make_service(
            order=order,
            fills=fills,
            scorecard_service=scorecard_svc,
        )
        report = await service.compute_for_order(_ORDER_ID)

        assert report is not None
        assert report.commission_cost_bps == Decimal("5.0000")

    @pytest.mark.asyncio
    async def test_falls_back_to_default_when_scorecard_none(self) -> None:
        order = _make_order(broker_id="broker-1")
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
        ]
        scorecard_svc = AsyncMock()
        scorecard_svc.get_scorecard = AsyncMock(return_value=None)

        service = _make_service(
            order=order,
            fills=fills,
            scorecard_service=scorecard_svc,
        )
        report = await service.compute_for_order(_ORDER_ID)

        assert report is not None
        assert report.commission_cost_bps == Decimal("5.0000")


# ---------------------------------------------------------------------------
# Event bus branch (lines 148-164)
# ---------------------------------------------------------------------------


class TestComputeWithEventBus:
    @pytest.mark.asyncio
    async def test_publishes_tca_computed_event(self) -> None:
        order = _make_order()
        fills = [
            _make_fill(datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)),
            _make_fill(datetime(2026, 4, 10, 10, 30, 0, tzinfo=timezone.utc)),
        ]
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        service = _make_service(order=order, fills=fills, event_bus=event_bus)
        report = await service.compute_for_order(_ORDER_ID)

        assert report is not None
        event_bus.publish.assert_awaited_once()
        call_args = event_bus.publish.call_args
        # First positional arg is the topic
        topic = call_args[0][0]
        assert "tca.computed" in topic
        # Second positional arg is the event
        event = call_args[0][1]
        assert event.data["order_id"] == str(_ORDER_ID)


# ---------------------------------------------------------------------------
# get_portfolio_report (lines 192-216)
# ---------------------------------------------------------------------------


class TestGetPortfolioReport:
    @pytest.mark.asyncio
    async def test_aggregates_tca_for_portfolio_orders(self) -> None:
        order1_id = "aaaa0000-0000-0000-0000-000000000001"
        order2_id = "aaaa0000-0000-0000-0000-000000000002"

        o1 = _make_order(id=order1_id, instrument_id="AAPL")
        o2 = _make_order(id=order2_id, instrument_id="GOOG")

        r1 = _make_tca_record(
            order_id=order1_id,
            total_cost_bps=Decimal("10.0000"),
            commission_cost_bps=Decimal("5.0000"),
            spread_cost_bps=Decimal("2.0000"),
            market_impact_cost_bps=Decimal("3.0000"),
            timing_cost_bps=Decimal("1.0000"),
            total_cost_usd=Decimal("100.00"),
        )
        r2 = _make_tca_record(
            order_id=order2_id,
            total_cost_bps=Decimal("20.0000"),
            commission_cost_bps=Decimal("7.0000"),
            spread_cost_bps=Decimal("4.0000"),
            market_impact_cost_bps=Decimal("6.0000"),
            timing_cost_bps=Decimal("3.0000"),
            total_cost_usd=Decimal("200.00"),
        )

        service = _make_service()
        # Override the repo methods for this test
        service._order_repo.get_by_portfolio = AsyncMock(return_value=[o1, o2])
        service._tca_repo.get_by_order_ids = AsyncMock(return_value=[r1, r2])

        report = await service.get_portfolio_report(_PORTFOLIO_ID)

        assert report.portfolio_id == _PORTFOLIO_ID
        assert report.total_orders == 2
        assert report.avg_total_cost_bps == Decimal("15.0000")
        assert report.avg_commission_bps == Decimal("6.0000")
        assert report.total_cost_usd == Decimal("300.00")
        assert len(report.orders) == 2

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_zeros(self) -> None:
        service = _make_service()
        service._order_repo.get_by_portfolio = AsyncMock(return_value=[])
        service._tca_repo.get_by_order_ids = AsyncMock(return_value=[])

        report = await service.get_portfolio_report(_PORTFOLIO_ID)

        assert report.total_orders == 0
        assert report.avg_total_cost_bps == _ZERO
        assert report.total_cost_usd == _ZERO
        assert report.orders == []

    @pytest.mark.asyncio
    async def test_skips_orders_without_tca_record(self) -> None:
        """Orders that have no matching TCA record are excluded."""
        o1_id = "aaaa0000-0000-0000-0000-000000000001"
        o2_id = "aaaa0000-0000-0000-0000-000000000002"

        o1 = _make_order(id=o1_id)
        o2 = _make_order(id=o2_id)

        r1 = _make_tca_record(
            order_id=o1_id,
            total_cost_bps=Decimal("10.0000"),
        )
        # No record for o2

        service = _make_service()
        service._order_repo.get_by_portfolio = AsyncMock(return_value=[o1, o2])
        service._tca_repo.get_by_order_ids = AsyncMock(return_value=[r1])

        report = await service.get_portfolio_report(_PORTFOLIO_ID)

        assert report.total_orders == 1
        assert len(report.orders) == 1


# ---------------------------------------------------------------------------
# get_fund_summary (lines 230-260)
# ---------------------------------------------------------------------------


class TestGetFundSummary:
    @pytest.mark.asyncio
    async def test_returns_summary_for_fund(self) -> None:
        order1_id = "bbbb0000-0000-0000-0000-000000000001"
        order2_id = "bbbb0000-0000-0000-0000-000000000002"

        o1 = MagicMock()
        o1.id = order1_id
        o2 = MagicMock()
        o2.id = order2_id

        r1 = _make_tca_record(
            order_id=order1_id,
            implementation_shortfall_bps=Decimal("12.0000"),
            commission_cost_bps=Decimal("5.0000"),
            spread_cost_bps=Decimal("3.0000"),
            market_impact_cost_bps=Decimal("4.0000"),
            total_cost_usd=Decimal("500.00"),
        )
        r2 = _make_tca_record(
            order_id=order2_id,
            implementation_shortfall_bps=Decimal("8.0000"),
            commission_cost_bps=Decimal("3.0000"),
            spread_cost_bps=Decimal("1.0000"),
            market_impact_cost_bps=Decimal("2.0000"),
            total_cost_usd=Decimal("300.00"),
        )

        # Mock the _session context manager + sqlalchemy query
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [o1, o2]
        mock_session.execute = AsyncMock(return_value=result_mock)

        service = _make_service()
        # Patch the _session on the order_repo to yield our mock_session
        service._order_repo._session = _mock_session_cm(mock_session)
        service._tca_repo.get_by_order_ids = AsyncMock(return_value=[r1, r2])

        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, tzinfo=timezone.utc)
        summary = await service.get_fund_summary("alpha", start, end)

        assert summary.fund_slug == "alpha"
        assert summary.total_orders_analyzed == 2
        assert summary.avg_implementation_shortfall_bps == Decimal("10.0000")
        assert summary.avg_commission_bps == Decimal("4.0000")
        assert summary.total_cost_usd == Decimal("800.00")

    @pytest.mark.asyncio
    async def test_empty_fund_returns_zeros(self) -> None:
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        service = _make_service()
        service._order_repo._session = _mock_session_cm(mock_session)
        service._tca_repo.get_by_order_ids = AsyncMock(return_value=[])

        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, tzinfo=timezone.utc)
        summary = await service.get_fund_summary("alpha", start, end)

        assert summary.total_orders_analyzed == 0
        assert summary.avg_implementation_shortfall_bps == _ZERO
        assert summary.total_cost_usd == _ZERO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


def _mock_session_cm(mock_session: AsyncMock):
    @asynccontextmanager
    async def _cm(session=None):
        yield mock_session

    return _cm
