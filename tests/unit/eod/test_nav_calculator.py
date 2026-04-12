"""Unit tests for NAVCalculator — the most important daily number."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.eod.core.nav_calculator import NAVCalculator

_PORT_ID = uuid4()
_BIZ_DATE = date(2026, 4, 11)


def _make_position(mv: Decimal, currency: str = "USD") -> MagicMock:
    p = MagicMock()
    p.market_value = mv
    p.currency = currency
    return p


def _make_balance(total: Decimal, currency: str = "USD") -> MagicMock:
    b = MagicMock()
    b.total_balance = total
    b.currency = currency
    return b


def _make_calculator(
    positions: list | None = None,
    balances: list | None = None,
    fee_summary: dict | None = None,
    total_shares: Decimal | None = None,
    fx_converter: MagicMock | None = None,
) -> tuple[NAVCalculator, AsyncMock]:
    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    cash_service = AsyncMock()
    cash_service.get_balances = AsyncMock(return_value=balances or [])

    nav_repo = AsyncMock()
    nav_repo.upsert = AsyncMock()

    fee_service = None
    if fee_summary is not None:
        fee_service = AsyncMock()
        fee_service.get_fee_summary = AsyncMock(return_value=fee_summary)

    capital_service = None
    if total_shares is not None:
        capital_service = AsyncMock()
        capital_service.get_total_shares = AsyncMock(return_value=total_shares)

    calc = NAVCalculator(
        position_service=position_service,
        cash_service=cash_service,
        nav_repo=nav_repo,
        fee_service=fee_service,
        capital_service=capital_service,
        fx_converter=fx_converter,
    )
    return calc, nav_repo


class TestNAVCalculation:
    @pytest.mark.asyncio
    async def test_nav_equals_positions_plus_cash(self) -> None:
        positions = [
            _make_position(Decimal("5000000")),
            _make_position(Decimal("3000000")),
        ]
        balances = [_make_balance(Decimal("2000000"))]
        calc, nav_repo = _make_calculator(positions=positions, balances=balances)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        # NAV = 5M + 3M + 2M = 10M
        assert result.nav == Decimal("10000000")
        assert result.net_market_value == Decimal("8000000")
        assert result.cash_balance == Decimal("2000000")
        nav_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_nav_subtracts_accrued_fees(self) -> None:
        positions = [_make_position(Decimal("10000000"))]
        balances = [_make_balance(Decimal("1000000"))]
        fees = {"management": Decimal("50000"), "performance": Decimal("100000")}
        calc, _ = _make_calculator(positions=positions, balances=balances, fee_summary=fees)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        # NAV = 10M + 1M - 150K = 10.85M
        assert result.nav == Decimal("10850000")
        assert result.accrued_fees == Decimal("150000")

    @pytest.mark.asyncio
    async def test_nav_per_share_with_real_shares(self) -> None:
        positions = [_make_position(Decimal("10000000"))]
        calc, _ = _make_calculator(
            positions=positions,
            total_shares=Decimal("5000"),
        )

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        # NAV per share = 10M / 5000 = 2000
        assert result.nav_per_share == Decimal("2000")
        assert result.shares_outstanding == Decimal("5000")

    @pytest.mark.asyncio
    async def test_nav_per_share_default_shares(self) -> None:
        """Without capital service, uses default 1000 shares."""
        positions = [_make_position(Decimal("10000000"))]
        calc, _ = _make_calculator(positions=positions)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.shares_outstanding == Decimal("1000")
        assert result.nav_per_share == Decimal("10000")

    @pytest.mark.asyncio
    async def test_empty_portfolio(self) -> None:
        calc, _ = _make_calculator()

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.nav == Decimal(0)
        assert result.gross_market_value == Decimal(0)
        assert result.net_market_value == Decimal(0)

    @pytest.mark.asyncio
    async def test_short_positions_reduce_net_increase_gross(self) -> None:
        positions = [
            _make_position(Decimal("8000000")),
            _make_position(Decimal("-2000000")),  # short
        ]
        calc, _ = _make_calculator(positions=positions)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.gross_market_value == Decimal("10000000")  # abs(8M) + abs(-2M)
        assert result.net_market_value == Decimal("6000000")  # 8M + (-2M)
        assert result.nav == Decimal("6000000")

    @pytest.mark.asyncio
    async def test_multi_currency_positions_with_fx(self) -> None:
        positions = [
            _make_position(Decimal("5000000"), currency="USD"),
            _make_position(Decimal("3000000"), currency="EUR"),
        ]
        fx = MagicMock()
        fx.convert = MagicMock(return_value=Decimal("3300000"))  # EUR→USD
        calc, _ = _make_calculator(positions=positions, fx_converter=fx)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        # 5M USD + 3.3M USD = 8.3M
        assert result.net_market_value == Decimal("8300000")

    @pytest.mark.asyncio
    async def test_multi_currency_cash_with_fx(self) -> None:
        balances = [
            _make_balance(Decimal("2000000"), "USD"),
            _make_balance(Decimal("1000000"), "EUR"),
        ]
        fx = MagicMock()
        fx.convert = MagicMock(return_value=Decimal("1100000"))  # EUR→USD
        calc, _ = _make_calculator(balances=balances, fx_converter=fx)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.cash_balance == Decimal("3100000")

    @pytest.mark.asyncio
    async def test_fx_fallback_when_rate_missing(self) -> None:
        """NAV still computes when FX rate is unavailable — uses unconverted amount."""
        positions = [_make_position(Decimal("3000000"), currency="GBP")]
        fx = MagicMock()
        fx.convert = MagicMock(return_value=None)
        calc, _ = _make_calculator(positions=positions, fx_converter=fx)

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        # Falls back to unconverted GBP amount
        assert result.net_market_value == Decimal("3000000")

    @pytest.mark.asyncio
    async def test_fee_service_failure_doesnt_break_nav(self) -> None:
        """Fee lookup failure is non-fatal — NAV uses 0 for fees."""
        positions = [_make_position(Decimal("10000000"))]
        fee_service = AsyncMock()
        fee_service.get_fee_summary = AsyncMock(side_effect=Exception("fee error"))

        calc = NAVCalculator(
            position_service=AsyncMock(
                get_by_portfolio=AsyncMock(return_value=positions)
            ),
            cash_service=AsyncMock(get_balances=AsyncMock(return_value=[])),
            nav_repo=AsyncMock(upsert=AsyncMock()),
            fee_service=fee_service,
        )

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.nav == Decimal("10000000")
        assert result.accrued_fees == Decimal(0)

    @pytest.mark.asyncio
    async def test_capital_service_failure_uses_default_shares(self) -> None:
        positions = [_make_position(Decimal("10000000"))]
        capital_service = AsyncMock()
        capital_service.get_total_shares = AsyncMock(side_effect=Exception("cap error"))

        calc = NAVCalculator(
            position_service=AsyncMock(
                get_by_portfolio=AsyncMock(return_value=positions)
            ),
            cash_service=AsyncMock(get_balances=AsyncMock(return_value=[])),
            nav_repo=AsyncMock(upsert=AsyncMock()),
            capital_service=capital_service,
        )

        result = await calc.calculate_nav(_PORT_ID, _BIZ_DATE)

        assert result.shares_outstanding == Decimal("1000")
