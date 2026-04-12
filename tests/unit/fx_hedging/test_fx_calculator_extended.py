"""Extended unit tests for FX calculator — cover missing line 193 (no spot skip)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.fx_hedging.core.calculator import recommend_hedges


class TestRecommendHedgesNoSpot:
    def test_skips_currency_without_spot(self) -> None:
        """When spots dict is missing a currency, that exposure is skipped."""
        recs = recommend_hedges(
            currency_exposures={"EUR": Decimal("5000000"), "GBP": Decimal("3000000")},
            base_currency="USD",
            spots={"EUR": Decimal("1.0800")},  # GBP intentionally missing
            domestic_rate=Decimal("0.05"),
            foreign_rates={"EUR": Decimal("0.04"), "GBP": Decimal("0.045")},
            hedge_ratio=Decimal("1.0"),
            tenor_days=30,
        )
        # Only EUR should have a recommendation, GBP skipped (no spot)
        assert len(recs) == 1
        assert recs[0].quote_currency == "EUR"
