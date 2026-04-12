"""Unit tests for ScorecardService — broker execution quality tracking."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.orders.services.scorecard import ScorecardService, _ema


def _make_scorecard_record(
    broker_id: str = "broker-1",
    total_orders: int = 10,
    total_fills: int = 8,
    total_rejects: int = 2,
    avg_slippage_bps: Decimal = Decimal("2.0"),
    avg_fill_time_ms: int = 150,
    avg_cost_bps: Decimal = Decimal("7.0"),
    fill_rate: Decimal = Decimal("0.8000"),
    instrument_class: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.broker_id = broker_id
    r.instrument_class = instrument_class
    r.total_orders = total_orders
    r.total_fills = total_fills
    r.total_rejects = total_rejects
    r.avg_slippage_bps = avg_slippage_bps
    r.avg_fill_time_ms = avg_fill_time_ms
    r.avg_cost_bps = avg_cost_bps
    r.fill_rate = fill_rate
    r.period_start = None
    r.period_end = None
    return r


def _new_scorecard_mock(**kwargs):
    """Return a mock that behaves like a fresh BrokerScorecardRecord with server_default=0."""
    r = MagicMock()
    r.id = kwargs.get("id", "new-id")
    r.broker_id = kwargs.get("broker_id", "broker")
    r.instrument_class = kwargs.get("instrument_class")
    r.total_orders = 0
    r.total_fills = 0
    r.total_rejects = 0
    r.avg_slippage_bps = Decimal(0)
    r.avg_fill_time_ms = 0
    r.avg_cost_bps = Decimal(0)
    r.fill_rate = Decimal(0)
    r.period_start = kwargs.get("period_start")
    r.period_end = None
    return r


def _make_service(
    existing_record: MagicMock | None = None,
    all_records: list | None = None,
) -> ScorecardService:
    scorecard_repo = AsyncMock()
    scorecard_repo.get_by_broker = AsyncMock(return_value=existing_record)
    scorecard_repo.upsert = AsyncMock()
    scorecard_repo.get_all = AsyncMock(return_value=all_records or [])

    session_factory = MagicMock()
    # fund_scope returns an async context manager yielding a mock session
    mock_session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    session_factory.fund_scope = MagicMock(return_value=cm)

    return ScorecardService(
        scorecard_repo=scorecard_repo,
        session_factory=session_factory,
    )


class TestEma:
    def test_basic_ema(self) -> None:
        result = _ema(Decimal("10"), Decimal("20"))
        # EMA with alpha=0.1: 10 * 0.9 + 20 * 0.1 = 9 + 2 = 11
        assert result == Decimal("11.00000000")

    def test_ema_from_zero(self) -> None:
        result = _ema(Decimal("0"), Decimal("100"))
        # 0 * 0.9 + 100 * 0.1 = 10
        assert result == Decimal("10.00000000")

    def test_ema_same_value(self) -> None:
        result = _ema(Decimal("50"), Decimal("50"))
        assert result == Decimal("50.00000000")


class TestRecordFill:
    @pytest.mark.asyncio
    async def test_updates_existing_record(self) -> None:
        record = _make_scorecard_record()
        svc = _make_service(existing_record=record)

        await svc.record_fill(
            broker_id="broker-1",
            slippage_bps=Decimal("1.5"),
            fill_time_ms=120,
            commission_bps=Decimal("3.0"),
            fund_slug="test-fund",
        )

        svc._scorecard_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_record_if_none(self) -> None:
        svc = _make_service(existing_record=None)

        with patch(
            "app.modules.orders.services.scorecard.BrokerScorecardRecord",
            side_effect=_new_scorecard_mock,
        ):
            await svc.record_fill(
                broker_id="new-broker",
                slippage_bps=Decimal("2.0"),
                fill_time_ms=200,
                commission_bps=Decimal("5.0"),
                fund_slug="test-fund",
            )

        svc._scorecard_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_increments_counters(self) -> None:
        record = _make_scorecard_record(total_orders=10, total_fills=8)
        svc = _make_service(existing_record=record)

        await svc.record_fill(
            broker_id="broker-1",
            slippage_bps=Decimal("1.5"),
            fill_time_ms=120,
            commission_bps=Decimal("3.0"),
            fund_slug="test-fund",
        )

        assert record.total_orders == 11
        assert record.total_fills == 9

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self) -> None:
        """Scorecard failures should not propagate."""
        svc = _make_service()
        svc._scorecard_repo.get_by_broker = AsyncMock(side_effect=RuntimeError("db error"))

        # Should not raise
        await svc.record_fill(
            broker_id="broker-1",
            slippage_bps=Decimal("1.5"),
            fill_time_ms=120,
            commission_bps=Decimal("3.0"),
            fund_slug="test-fund",
        )

    @pytest.mark.asyncio
    async def test_with_instrument_class(self) -> None:
        svc = _make_service(existing_record=None)

        with patch(
            "app.modules.orders.services.scorecard.BrokerScorecardRecord",
            side_effect=_new_scorecard_mock,
        ):
            await svc.record_fill(
                broker_id="broker-1",
                slippage_bps=Decimal("1.5"),
                fill_time_ms=120,
                commission_bps=Decimal("3.0"),
                fund_slug="test-fund",
                instrument_class="equity",
            )

        svc._scorecard_repo.upsert.assert_called_once()


class TestRecordReject:
    @pytest.mark.asyncio
    async def test_updates_existing_record(self) -> None:
        record = _make_scorecard_record(total_orders=10, total_rejects=2)
        svc = _make_service(existing_record=record)

        await svc.record_reject(broker_id="broker-1", fund_slug="test-fund")

        assert record.total_orders == 11
        assert record.total_rejects == 3
        svc._scorecard_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_on_reject(self) -> None:
        svc = _make_service(existing_record=None)

        with patch(
            "app.modules.orders.services.scorecard.BrokerScorecardRecord",
            side_effect=_new_scorecard_mock,
        ):
            await svc.record_reject(broker_id="new-broker", fund_slug="test-fund")

        svc._scorecard_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self) -> None:
        svc = _make_service()
        svc._scorecard_repo.get_by_broker = AsyncMock(side_effect=RuntimeError("fail"))

        await svc.record_reject(broker_id="broker-1", fund_slug="test-fund")


class TestGetScorecard:
    @pytest.mark.asyncio
    async def test_returns_scorecard(self) -> None:
        record = _make_scorecard_record()
        svc = _make_service(existing_record=record)

        result = await svc.get_scorecard("broker-1", "test-fund")

        assert result is not None
        assert result.broker_id == "broker-1"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        svc = _make_service(existing_record=None)

        result = await svc.get_scorecard("unknown", "test-fund")

        assert result is None


class TestGetAllScorecards:
    @pytest.mark.asyncio
    async def test_returns_all(self) -> None:
        records = [_make_scorecard_record("b-1"), _make_scorecard_record("b-2")]
        svc = _make_service(all_records=records)

        result = await svc.get_all_scorecards("test-fund")

        assert len(result) == 2
