"""Unit tests for PnLSnapshotService — daily P&L freeze."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.eod.core.pnl_snapshot import PnLSnapshotService

_PORT_ID = uuid4()
_BIZ_DATE = date(2026, 4, 11)


def _make_position(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("25000"),
    market_price: Decimal = Decimal("250"),
    unrealized_pnl: Decimal = Decimal("2500"),
    cost_basis: Decimal = Decimal("22500"),
    currency: str = "USD",
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    p.market_price = market_price
    p.unrealized_pnl = unrealized_pnl
    p.cost_basis = cost_basis
    p.currency = currency
    p.realized_pnl = Decimal("0")
    return p


def _make_service(
    positions: list | None = None,
    fx_converter: MagicMock | None = None,
    with_daily_pnl_repo: bool = False,
) -> tuple[PnLSnapshotService, AsyncMock, AsyncMock | None]:
    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    pnl_repo = AsyncMock()
    pnl_repo.upsert = AsyncMock()

    daily_pnl_repo = None
    if with_daily_pnl_repo:
        daily_pnl_repo = AsyncMock()
        daily_pnl_repo.upsert_batch = AsyncMock()

    svc = PnLSnapshotService(
        position_service=position_service,
        pnl_repo=pnl_repo,
        daily_pnl_repo=daily_pnl_repo,
        fx_converter=fx_converter,
    )
    return svc, pnl_repo, daily_pnl_repo


class TestPnLSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_basic(self) -> None:
        positions = [
            _make_position("AAPL", unrealized_pnl=Decimal("2500")),
            _make_position("MSFT", unrealized_pnl=Decimal("-500")),
        ]
        svc, pnl_repo, _ = _make_service(positions)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE)

        assert result.portfolio_id == _PORT_ID
        assert result.business_date == _BIZ_DATE
        assert result.total_unrealized_pnl == Decimal("2000")
        assert result.total_realized_pnl == Decimal("0")
        assert result.total_pnl == Decimal("2000")
        assert result.position_count == 2
        pnl_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_portfolio(self) -> None:
        svc, pnl_repo, _ = _make_service([])

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE)

        assert result.total_pnl == Decimal("0")
        assert result.position_count == 0
        pnl_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_fx_conversion(self) -> None:
        positions = [
            _make_position("VOD.L", unrealized_pnl=Decimal("1000"), currency="GBP"),
        ]
        fx = MagicMock()
        fx.convert = MagicMock(return_value=Decimal("1260"))  # GBP→USD
        svc, pnl_repo, _ = _make_service(positions, fx_converter=fx)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE, base_currency="USD")

        assert result.total_unrealized_pnl == Decimal("1260")
        fx.convert.assert_called_once_with(Decimal("1000"), "GBP", "USD")

    @pytest.mark.asyncio
    async def test_fx_fallback_when_rate_missing(self) -> None:
        positions = [
            _make_position("VOD.L", unrealized_pnl=Decimal("1000"), currency="GBP"),
        ]
        fx = MagicMock()
        fx.convert = MagicMock(return_value=None)
        svc, _, _ = _make_service(positions, fx_converter=fx)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE)

        # Falls back to unconverted amount
        assert result.total_unrealized_pnl == Decimal("1000")

    @pytest.mark.asyncio
    async def test_same_currency_skips_fx(self) -> None:
        positions = [
            _make_position("AAPL", unrealized_pnl=Decimal("500"), currency="USD"),
        ]
        fx = MagicMock()
        svc, _, _ = _make_service(positions, fx_converter=fx)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE, base_currency="USD")

        assert result.total_unrealized_pnl == Decimal("500")
        fx.convert.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_pnl_records_written(self) -> None:
        positions = [
            _make_position("AAPL"),
            _make_position("MSFT"),
        ]
        svc, _, daily_pnl_repo = _make_service(positions, with_daily_pnl_repo=True)

        await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE)

        daily_pnl_repo.upsert_batch.assert_called_once()
        records = daily_pnl_repo.upsert_batch.call_args.args[0]
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_daily_pnl_not_written_when_repo_missing(self) -> None:
        positions = [_make_position("AAPL")]
        svc, pnl_repo, _ = _make_service(positions, with_daily_pnl_repo=False)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE)

        # No error, still produces snapshot
        assert result.position_count == 1
        pnl_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_currency_aggregation(self) -> None:
        positions = [
            _make_position("AAPL", unrealized_pnl=Decimal("3000"), currency="USD"),
            _make_position("SAP", unrealized_pnl=Decimal("2000"), currency="EUR"),
            _make_position("VOD.L", unrealized_pnl=Decimal("1000"), currency="GBP"),
        ]
        fx = MagicMock()
        fx.convert = MagicMock(side_effect=lambda amt, src, tgt: amt * Decimal("1.1"))
        svc, _, _ = _make_service(positions, fx_converter=fx)

        result = await svc.snapshot_pnl(_PORT_ID, _BIZ_DATE, base_currency="USD")

        # USD: 3000 (no conversion) + EUR: 2000*1.1=2200 + GBP: 1000*1.1=1100
        assert result.total_unrealized_pnl == Decimal("6300")
