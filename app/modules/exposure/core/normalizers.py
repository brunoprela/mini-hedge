"""Per-asset-class exposure normalizers.

Different asset classes contribute to portfolio exposure differently:
- Equities/ETFs: quantity x price x fx_rate
- Options: delta-adjusted (contracts x delta x underlying_price x multiplier x fx_rate)
- Futures: notional (contracts x contract_size x price x fx_rate)
- Fixed income: par x clean_price / 100 + accrued x fx_rate
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.modules.exposure.interfaces import PositionValue

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)


class ExposureNormalizer(Protocol):
    """Converts a position into its effective market exposure."""

    def normalize(self, position: PositionValue, *, fx_rate: Decimal = ONE) -> Decimal:
        """Return the delta-equivalent market exposure in base currency."""
        ...


class EquityExposureNormalizer:
    """Equities/ETFs: exposure = quantity x price x fx_rate."""

    def normalize(self, position: PositionValue, *, fx_rate: Decimal = ONE) -> Decimal:
        return position.quantity * position.market_price * fx_rate


class OptionExposureNormalizer:
    """Options: delta-adjusted exposure = contracts x delta x underlying_price x multiplier x fx_rate.

    Falls back to market_value when delta/underlying_price are unavailable (position
    metadata not yet enriched from pricing).
    """

    def normalize(self, position: PositionValue, *, fx_rate: Decimal = ONE) -> Decimal:
        # PositionValue doesn't carry greeks yet — use market_value as fallback
        return position.market_value * fx_rate


class FutureExposureNormalizer:
    """Futures: notional exposure = contracts x contract_size x price x fx_rate.

    Falls back to market_value when contract_size is unavailable.
    """

    def normalize(self, position: PositionValue, *, fx_rate: Decimal = ONE) -> Decimal:
        # PositionValue doesn't carry contract_size yet — use market_value as fallback
        return position.market_value * fx_rate


class FixedIncomeExposureNormalizer:
    """Bonds: market value exposure = par_held x clean_price / 100 x fx_rate.

    Falls back to market_value when par/accrued data is unavailable.
    """

    def normalize(self, position: PositionValue, *, fx_rate: Decimal = ONE) -> Decimal:
        # PositionValue doesn't carry accrued_interest yet — use market_value as fallback
        return position.market_value * fx_rate


# Default registry — maps AssetClass values to their normalizer
EXPOSURE_NORMALIZERS: dict[str, ExposureNormalizer] = {
    "equity": EquityExposureNormalizer(),
    "etf": EquityExposureNormalizer(),
    "option": OptionExposureNormalizer(),
    "future": FutureExposureNormalizer(),
    "fixed_income": FixedIncomeExposureNormalizer(),
    "fx": EquityExposureNormalizer(),
    "fx_forward": EquityExposureNormalizer(),
    "swap": EquityExposureNormalizer(),
    "private": EquityExposureNormalizer(),
}

_FALLBACK = EquityExposureNormalizer()


def normalize_exposure(
    position: PositionValue,
    *,
    fx_rate: Decimal = ONE,
    normalizers: dict[str, ExposureNormalizer] | None = None,
) -> Decimal:
    """Normalize a position's exposure using the appropriate asset-class normalizer."""
    registry = normalizers or EXPOSURE_NORMALIZERS
    asset_class = (position.asset_class or "").lower()
    normalizer = registry.get(asset_class, _FALLBACK)
    return normalizer.normalize(position, fx_rate=fx_rate)
