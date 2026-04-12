"""Unit tests for PositionService — position queries, lots, PnL, point-in-time."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.positions.services.position import PositionService

_PORT_ID = uuid4()


def _make_position_record(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("25000"),
) -> MagicMock:
    r = MagicMock()
    r.portfolio_id = str(_PORT_ID)
    r.instrument_id = instrument_id
    r.quantity = quantity
    r.avg_cost = Decimal("200")
    r.cost_basis = Decimal("20000")
    r.market_price = Decimal("250")
    r.market_value = market_value
    r.unrealized_pnl = market_value - Decimal("20000")
    r.currency = "USD"
    r.last_updated = datetime.now(timezone.utc)
    return r


def _make_lot_record(instrument_id: str = "AAPL") -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.portfolio_id = str(_PORT_ID)
    r.instrument_id = instrument_id
    r.quantity = Decimal("50")
    r.original_quantity = Decimal("100")
    r.price = Decimal("200")
    r.acquired_at = datetime.now(timezone.utc)
    r.trade_id = str(uuid4())
    return r


def _make_service(
    positions: list | None = None,
    lots: list | None = None,
    summary: dict | None = None,
    with_event_store: bool = False,
    with_daily_pnl: bool = False,
) -> PositionService:
    position_repo = AsyncMock()
    position_repo.get_position = AsyncMock(
        return_value=positions[0] if positions else None
    )
    position_repo.get_by_portfolio = AsyncMock(return_value=positions or [])
    position_repo.get_portfolio_summary = AsyncMock(return_value=summary)

    lot_repo = AsyncMock()
    lot_repo.get_lots = AsyncMock(return_value=lots or [])

    trade_handler = AsyncMock()
    trade_handler.handle_trade = AsyncMock()

    event_store = None
    if with_event_store:
        event_store = AsyncMock()

    daily_pnl_repo = None
    if with_daily_pnl:
        daily_pnl_repo = AsyncMock()

    return PositionService(
        position_repo=position_repo,
        lot_repo=lot_repo,
        trade_handler=trade_handler,
        event_store=event_store,
        daily_pnl_repo=daily_pnl_repo,
    )


class TestGetPosition:
    @pytest.mark.asyncio
    async def test_returns_position(self) -> None:
        record = _make_position_record("AAPL")
        svc = _make_service(positions=[record])

        result = await svc.get_position(_PORT_ID, "AAPL")

        assert result is not None
        assert result.instrument_id == "AAPL"
        assert result.portfolio_id == _PORT_ID
        assert result.quantity == Decimal("100")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        svc = _make_service(positions=None)

        result = await svc.get_position(_PORT_ID, "MISSING")

        assert result is None


class TestGetByPortfolio:
    @pytest.mark.asyncio
    async def test_returns_all_positions(self) -> None:
        records = [
            _make_position_record("AAPL"),
            _make_position_record("MSFT", market_value=Decimal("15000")),
        ]
        svc = _make_service(positions=records)

        result = await svc.get_by_portfolio(_PORT_ID)

        assert len(result) == 2
        assert result[0].instrument_id == "AAPL"
        assert result[1].instrument_id == "MSFT"

    @pytest.mark.asyncio
    async def test_empty_portfolio(self) -> None:
        svc = _make_service(positions=[])

        result = await svc.get_by_portfolio(_PORT_ID)

        assert result == []


class TestGetLots:
    @pytest.mark.asyncio
    async def test_returns_lots(self) -> None:
        lots = [_make_lot_record("AAPL"), _make_lot_record("AAPL")]
        svc = _make_service(lots=lots)

        result = await svc.get_lots(_PORT_ID, "AAPL")

        assert len(result) == 2
        assert result[0].instrument_id == "AAPL"

    @pytest.mark.asyncio
    async def test_no_lot_repo_returns_empty(self) -> None:
        svc = PositionService(
            position_repo=AsyncMock(),
            lot_repo=None,
            trade_handler=AsyncMock(),
        )

        result = await svc.get_lots(_PORT_ID, "AAPL")

        assert result == []


class TestGetPortfolioSummary:
    @pytest.mark.asyncio
    async def test_returns_summary(self) -> None:
        summary = {
            "total_market_value": Decimal("50000"),
            "total_cost_basis": Decimal("40000"),
            "total_realized_pnl": Decimal("5000"),
            "total_unrealized_pnl": Decimal("10000"),
            "position_count": 3,
        }
        svc = _make_service(summary=summary)

        result = await svc.get_portfolio_summary(_PORT_ID)

        assert result.total_market_value == Decimal("50000")
        assert result.position_count == 3
        assert result.portfolio_id == _PORT_ID

    @pytest.mark.asyncio
    async def test_empty_summary_returns_zeros(self) -> None:
        svc = _make_service(summary=None)

        result = await svc.get_portfolio_summary(_PORT_ID)

        assert result.total_market_value == Decimal(0)
        assert result.position_count == 0
        assert result.portfolio_id == _PORT_ID


class TestGetPositionAt:
    @pytest.mark.asyncio
    async def test_returns_none_without_event_store(self) -> None:
        svc = _make_service()

        result = await svc.get_position_at(_PORT_ID, "AAPL", datetime.now(timezone.utc))

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_events(self) -> None:
        svc = _make_service(with_event_store=True)
        svc._event_store.get_by_aggregate = AsyncMock(return_value=[])

        result = await svc.get_position_at(_PORT_ID, "AAPL", datetime.now(timezone.utc))

        assert result is None


class TestGetPortfolioPnl:
    @pytest.mark.asyncio
    async def test_returns_empty_without_daily_pnl_repo(self) -> None:
        svc = _make_service()

        result = await svc.get_portfolio_pnl(_PORT_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_aggregates_by_date(self) -> None:
        svc = _make_service(with_daily_pnl=True)

        rec1 = MagicMock()
        rec1.business_date = date(2026, 4, 10)
        rec1.realized_pnl = Decimal("100")
        rec1.unrealized_pnl = Decimal("200")
        rec1.currency = "USD"

        rec2 = MagicMock()
        rec2.business_date = date(2026, 4, 10)
        rec2.realized_pnl = Decimal("50")
        rec2.unrealized_pnl = Decimal("150")
        rec2.currency = "USD"

        rec3 = MagicMock()
        rec3.business_date = date(2026, 4, 11)
        rec3.realized_pnl = Decimal("300")
        rec3.unrealized_pnl = Decimal("400")
        rec3.currency = "USD"

        svc._daily_pnl_repo.get_by_portfolio = AsyncMock(return_value=[rec1, rec2, rec3])

        result = await svc.get_portfolio_pnl(_PORT_ID)

        assert len(result) == 2
        # First day: 100+50=150 realized, 200+150=350 unrealized
        assert result[0].date == date(2026, 4, 10)
        assert result[0].realized_pnl == Decimal("150")
        assert result[0].unrealized_pnl == Decimal("350")
        assert result[0].total_pnl == Decimal("500")
        # Second day
        assert result[1].date == date(2026, 4, 11)
        assert result[1].total_pnl == Decimal("700")
