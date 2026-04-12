"""Unit tests for position strategies — Equity, FixedIncome, Option, Future."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.positions.core.strategy import (
    EquityPositionStrategy,
    FixedIncomePositionStrategy,
    FuturePositionStrategy,
    OptionPositionStrategy,
    get_position_strategy,
)
from app.shared.types import AssetClass


# ------------------------------------------------------------------
# EquityPositionStrategy (existing, but adding coverage)
# ------------------------------------------------------------------


class TestEquityPositionStrategy:
    strat = EquityPositionStrategy()

    def test_market_value_long(self) -> None:
        assert self.strat.market_value(Decimal("100"), Decimal("150.50")) == Decimal("15050.00")

    def test_market_value_short(self) -> None:
        # Absolute exposure
        assert self.strat.market_value(Decimal("-100"), Decimal("150.50")) == Decimal("15050.00")

    def test_unrealized_pnl_long_profit(self) -> None:
        # Bought at cost_basis=14000 (100 shares * 140), now at 150
        pnl = self.strat.unrealized_pnl(Decimal("100"), Decimal("14000"), Decimal("150"))
        assert pnl == Decimal("1000")  # 15000 - 14000

    def test_unrealized_pnl_long_loss(self) -> None:
        pnl = self.strat.unrealized_pnl(Decimal("100"), Decimal("16000"), Decimal("150"))
        assert pnl == Decimal("-1000")  # 15000 - 16000

    def test_unrealized_pnl_short_profit(self) -> None:
        # Shorted at cost_basis=16000, price dropped to 150
        pnl = self.strat.unrealized_pnl(Decimal("-100"), Decimal("16000"), Decimal("150"))
        assert pnl == Decimal("1000")  # 16000 - 15000


# ------------------------------------------------------------------
# FixedIncomePositionStrategy
# ------------------------------------------------------------------


class TestFixedIncomePositionStrategy:
    strat = FixedIncomePositionStrategy()

    def test_market_value_at_par(self) -> None:
        # 1M par at 100 (par) = 1M
        mv = self.strat.market_value(Decimal("1000000"), Decimal("100"))
        assert mv == Decimal("1000000")

    def test_market_value_at_discount(self) -> None:
        # 1M par at 95 = 950,000
        mv = self.strat.market_value(Decimal("1000000"), Decimal("95"))
        assert mv == Decimal("950000")

    def test_market_value_with_accrued_interest(self) -> None:
        # 1M par at 98, accrued = 5000
        mv = self.strat.market_value(
            Decimal("1000000"), Decimal("98"), accrued_interest=Decimal("5000")
        )
        assert mv == Decimal("985000")  # 980000 + 5000

    def test_market_value_at_premium(self) -> None:
        # 1M par at 105 = 1,050,000
        mv = self.strat.market_value(Decimal("1000000"), Decimal("105"))
        assert mv == Decimal("1050000")

    def test_unrealized_pnl_gain(self) -> None:
        # Bought 1M par at cost=98, now at 101, accrued=2000
        pnl = self.strat.unrealized_pnl(
            Decimal("1000000"), Decimal("98"), Decimal("101"), accrued_interest=Decimal("2000")
        )
        # dirty_value = 1M * 101 / 100 + 2000 = 1,012,000
        # cost = 1M * 98 / 100 = 980,000
        assert pnl == Decimal("32000")

    def test_unrealized_pnl_loss(self) -> None:
        # Bought at 100, dropped to 95, no accrued
        pnl = self.strat.unrealized_pnl(Decimal("1000000"), Decimal("100"), Decimal("95"))
        # dirty = 950,000, cost = 1,000,000
        assert pnl == Decimal("-50000")

    def test_zero_accrued_default(self) -> None:
        # Should default to 0 accrued
        mv = self.strat.market_value(Decimal("500000"), Decimal("100"))
        assert mv == Decimal("500000")


# ------------------------------------------------------------------
# OptionPositionStrategy
# ------------------------------------------------------------------


class TestOptionPositionStrategy:
    strat = OptionPositionStrategy()

    def test_market_value_default_multiplier(self) -> None:
        # 10 contracts at $5.00 premium, default multiplier 100
        mv = self.strat.market_value(Decimal("10"), Decimal("5.00"))
        assert mv == Decimal("5000.00")  # 10 * 5 * 100

    def test_market_value_custom_multiplier(self) -> None:
        # SPX options: multiplier=100, 5 contracts at $25
        mv = self.strat.market_value(
            Decimal("5"), Decimal("25"), contract_multiplier=Decimal("100")
        )
        assert mv == Decimal("12500")

    def test_market_value_mini_options(self) -> None:
        # Mini options: multiplier=10
        mv = self.strat.market_value(
            Decimal("10"), Decimal("3.50"), contract_multiplier=Decimal("10")
        )
        assert mv == Decimal("350.00")

    def test_unrealized_pnl_profit(self) -> None:
        # Bought 10 calls at $3, now $5, multiplier=100
        pnl = self.strat.unrealized_pnl(Decimal("10"), Decimal("3"), Decimal("5"))
        assert pnl == Decimal("2000")  # 10 * (5 - 3) * 100

    def test_unrealized_pnl_loss(self) -> None:
        # Bought 10 calls at $5, now $2, multiplier=100
        pnl = self.strat.unrealized_pnl(Decimal("10"), Decimal("5"), Decimal("2"))
        assert pnl == Decimal("-3000")  # 10 * (2 - 5) * 100

    def test_unrealized_pnl_short_option(self) -> None:
        # Sold (short) 5 puts at $4, now $2 — profit
        pnl = self.strat.unrealized_pnl(Decimal("-5"), Decimal("4"), Decimal("2"))
        assert pnl == Decimal("1000")  # -5 * (2 - 4) * 100 = 1000


# ------------------------------------------------------------------
# FuturePositionStrategy
# ------------------------------------------------------------------


class TestFuturePositionStrategy:
    strat = FuturePositionStrategy()

    def test_market_value_default_size(self) -> None:
        # 5 contracts at 4500, default contract_size=1
        mv = self.strat.market_value(Decimal("5"), Decimal("4500"))
        assert mv == Decimal("22500")

    def test_market_value_with_contract_size(self) -> None:
        # ES futures: 2 contracts at 4500, size=50
        mv = self.strat.market_value(
            Decimal("2"), Decimal("4500"), contract_size=Decimal("50")
        )
        assert mv == Decimal("450000")  # 2 * 4500 * 50

    def test_market_value_crude_oil(self) -> None:
        # CL futures: 3 contracts at $75, contract_size=1000 barrels
        mv = self.strat.market_value(
            Decimal("3"), Decimal("75"), contract_size=Decimal("1000")
        )
        assert mv == Decimal("225000")

    def test_unrealized_pnl_long_profit(self) -> None:
        # Long 2 ES at 4400, now 4500, size=50
        pnl = self.strat.unrealized_pnl(
            Decimal("2"), Decimal("4400"), Decimal("4500"), contract_size=Decimal("50")
        )
        assert pnl == Decimal("10000")  # 2 * (4500 - 4400) * 50

    def test_unrealized_pnl_short_profit(self) -> None:
        # Short 3 CL at 80, dropped to 75, size=1000
        pnl = self.strat.unrealized_pnl(
            Decimal("-3"), Decimal("80"), Decimal("75"), contract_size=Decimal("1000")
        )
        assert pnl == Decimal("15000")  # -3 * (75 - 80) * 1000 = 15000

    def test_unrealized_pnl_loss(self) -> None:
        # Long 1 at 4500, dropped to 4400, size=50
        pnl = self.strat.unrealized_pnl(
            Decimal("1"), Decimal("4500"), Decimal("4400"), contract_size=Decimal("50")
        )
        assert pnl == Decimal("-5000")


# ------------------------------------------------------------------
# Strategy registry
# ------------------------------------------------------------------


class TestStrategyRegistry:
    def test_equity_registered(self) -> None:
        assert isinstance(get_position_strategy(AssetClass.EQUITY), EquityPositionStrategy)

    def test_etf_uses_equity(self) -> None:
        assert isinstance(get_position_strategy(AssetClass.ETF), EquityPositionStrategy)

    def test_fixed_income_registered(self) -> None:
        assert isinstance(get_position_strategy(AssetClass.FIXED_INCOME), FixedIncomePositionStrategy)

    def test_option_registered(self) -> None:
        assert isinstance(get_position_strategy(AssetClass.OPTION), OptionPositionStrategy)

    def test_future_registered(self) -> None:
        assert isinstance(get_position_strategy(AssetClass.FUTURE), FuturePositionStrategy)

    def test_unregistered_raises(self) -> None:
        with pytest.raises(KeyError, match="No position strategy"):
            get_position_strategy(AssetClass.SWAP)
