"""Unit tests for position calculation strategies."""

from decimal import Decimal

import pytest

from app.modules.positions.strategy import EquityPositionStrategy, get_position_strategy
from app.shared.types import AssetClass


class TestEquityPositionStrategy:
    def setup_method(self) -> None:
        self.strategy = EquityPositionStrategy()

    def test_market_value_long(self) -> None:
        mv = self.strategy.market_value(Decimal("100"), Decimal("150"))
        assert mv == Decimal("15000")

    def test_market_value_short(self) -> None:
        """Short positions: market_value is absolute exposure."""
        mv = self.strategy.market_value(Decimal("-100"), Decimal("150"))
        assert mv == Decimal("15000")

    def test_unrealized_pnl_long_profit(self) -> None:
        # Bought 100 @ $100 = $10,000 cost. Now at $120.
        pnl = self.strategy.unrealized_pnl(Decimal("100"), Decimal("10000"), Decimal("120"))
        assert pnl == Decimal("2000")

    def test_unrealized_pnl_long_loss(self) -> None:
        pnl = self.strategy.unrealized_pnl(Decimal("100"), Decimal("10000"), Decimal("80"))
        assert pnl == Decimal("-2000")

    def test_unrealized_pnl_short_profit(self) -> None:
        """Short: sold 100 @ $150 = $15,000 cost_basis. Price drops to $140."""
        pnl = self.strategy.unrealized_pnl(Decimal("-100"), Decimal("15000"), Decimal("140"))
        # cost_basis - mv = 15000 - 14000 = 1000 profit
        assert pnl == Decimal("1000")

    def test_unrealized_pnl_short_loss(self) -> None:
        """Short: sold 100 @ $150 = $15,000 cost_basis. Price rises to $160."""
        pnl = self.strategy.unrealized_pnl(Decimal("-100"), Decimal("15000"), Decimal("160"))
        # cost_basis - mv = 15000 - 16000 = -1000 loss
        assert pnl == Decimal("-1000")


class TestStrategyRegistry:
    def test_equity_registered(self) -> None:
        strategy = get_position_strategy(AssetClass.EQUITY)
        assert isinstance(strategy, EquityPositionStrategy)

    def test_etf_registered(self) -> None:
        strategy = get_position_strategy(AssetClass.ETF)
        assert isinstance(strategy, EquityPositionStrategy)

    def test_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="No position strategy"):
            get_position_strategy(AssetClass.FX)
