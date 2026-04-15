"""FX conversion utility — in-memory rate cache with triangulation.

All rates are stored as USD-based: 1 USD = X units of quote currency.
Cross rates are derived via triangulation:
  GBP → JPY = (USD/JPY) / (USD/GBP)
"""

from __future__ import annotations

from decimal import Decimal

import structlog

logger = structlog.get_logger()

ONE = Decimal(1)


class FXConverter:
    """Thread-safe FX rate cache with lazy triangulation."""

    def __init__(self) -> None:
        # key: "USD/GBP", value: rate (1 USD = rate GBP)
        self._rates: dict[str, Decimal] = {}

    def update_rate(self, base: str, quote: str, rate: Decimal) -> None:
        """Update the cached rate for a currency pair."""
        self._rates[f"{base}/{quote}"] = rate

    def get_rate(self, from_ccy: str, to_ccy: str) -> Decimal | None:
        """Get the conversion rate: 1 from_ccy = X to_ccy.

        Supports direct lookup and USD triangulation.
        Returns None if rate is unavailable.
        """
        if from_ccy == to_ccy:
            return ONE

        # Direct lookup: USD → X
        direct = self._rates.get(f"{from_ccy}/{to_ccy}")
        if direct is not None:
            return direct

        # Inverse: X → USD (if we have USD/X, invert)
        inverse = self._rates.get(f"{to_ccy}/{from_ccy}")
        if inverse is not None and inverse != 0:
            return ONE / inverse

        # Triangulation via USD
        # from_ccy → USD → to_ccy
        from_to_usd = self._rate_to_usd(from_ccy)
        usd_to_target = self._rate_from_usd(to_ccy)
        if from_to_usd is not None and usd_to_target is not None and usd_to_target != 0:
            return from_to_usd * usd_to_target

        logger.warning("fx_rate_not_found", from_ccy=from_ccy, to_ccy=to_ccy)
        return None

    def convert(self, amount: Decimal, from_ccy: str, to_ccy: str) -> Decimal | None:
        """Convert amount from one currency to another.

        Returns None if the rate is unavailable.
        """
        rate = self.get_rate(from_ccy, to_ccy)
        if rate is None:
            return None
        return amount * rate

    def _rate_to_usd(self, ccy: str) -> Decimal | None:
        """Get rate: 1 ccy = X USD."""
        if ccy == "USD":
            return ONE
        # We store USD/ccy, so ccy→USD = 1 / (USD/ccy)
        usd_to_ccy = self._rates.get(f"USD/{ccy}")
        if usd_to_ccy is not None and usd_to_ccy != 0:
            return ONE / usd_to_ccy
        return None

    def _rate_from_usd(self, ccy: str) -> Decimal | None:
        """Get rate: 1 USD = X ccy."""
        if ccy == "USD":
            return ONE
        return self._rates.get(f"USD/{ccy}")

    @property
    def available_pairs(self) -> list[str]:
        """List all pairs with cached rates."""
        return sorted(self._rates.keys())
