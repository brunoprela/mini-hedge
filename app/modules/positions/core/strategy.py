"""Asset-class-specific position calculation strategies.

Different asset classes calculate market value and P&L differently.
The PositionStrategy protocol defines the interface; each asset class
provides an implementation. Phase 0 includes only EquityPositionStrategy.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from app.shared.types import AssetClass


class PositionStrategy(Protocol):
    """Asset-class-specific position value calculation."""

    def market_value(self, quantity: Decimal, market_price: Decimal, **kwargs: Any) -> Decimal:
        """Calculate the market value of a position."""
        ...

    def unrealized_pnl(
        self,
        quantity: Decimal,
        cost_basis: Decimal,
        market_price: Decimal,
        **kwargs: Any,
    ) -> Decimal:
        """Calculate unrealized P&L."""
        ...


class EquityPositionStrategy:
    """Equities and ETFs: value = quantity × price.

    For short positions (negative quantity), market_value is the absolute
    exposure and unrealized P&L is cost_basis - |market_value| (profit
    when price drops below entry).
    """

    def market_value(self, quantity: Decimal, market_price: Decimal, **kwargs: Any) -> Decimal:
        return abs(quantity) * market_price

    def unrealized_pnl(
        self,
        quantity: Decimal,
        cost_basis: Decimal,
        market_price: Decimal,
        **kwargs: Any,
    ) -> Decimal:
        mv = abs(quantity) * market_price
        if quantity < 0:
            return cost_basis - mv  # Short: profit when price drops
        return mv - cost_basis


# Registry: maps asset class to strategy implementation.
# New asset classes register here — no changes to aggregate or handlers.
POSITION_STRATEGIES: dict[AssetClass, PositionStrategy] = {
    AssetClass.EQUITY: EquityPositionStrategy(),
    AssetClass.ETF: EquityPositionStrategy(),
}


def get_position_strategy(asset_class: AssetClass) -> PositionStrategy:
    """Look up the strategy for an asset class.

    Raises KeyError if no strategy is registered for the given asset class.
    """
    try:
        return POSITION_STRATEGIES[asset_class]
    except KeyError:
        raise KeyError(
            f"No position strategy registered for asset class '{asset_class}'. "
            f"Registered: {sorted(POSITION_STRATEGIES.keys())}"
        ) from None
