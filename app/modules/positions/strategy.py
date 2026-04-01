"""Asset-class-specific position calculation strategies.

Different asset classes calculate market value and P&L differently.
The PositionStrategy protocol defines the interface; each asset class
provides an implementation. Phase 0 includes only EquityPositionStrategy.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol


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
    """Equities and ETFs: value = quantity × price."""

    def market_value(self, quantity: Decimal, market_price: Decimal, **kwargs: Any) -> Decimal:
        return quantity * market_price

    def unrealized_pnl(
        self,
        quantity: Decimal,
        cost_basis: Decimal,
        market_price: Decimal,
        **kwargs: Any,
    ) -> Decimal:
        return quantity * market_price - cost_basis


# Registry: maps asset class to strategy implementation.
# New asset classes register here — no changes to aggregate or handlers.
POSITION_STRATEGIES: dict[str, PositionStrategy] = {
    "equity": EquityPositionStrategy(),
    "etf": EquityPositionStrategy(),
}


def get_position_strategy(asset_class: str) -> PositionStrategy:
    """Look up the strategy for an asset class, defaulting to equity."""
    return POSITION_STRATEGIES.get(asset_class, POSITION_STRATEGIES["equity"])
