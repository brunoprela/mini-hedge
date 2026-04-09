"""Unit tests for exposure calculator — pure functions, no I/O."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.exposure.core.calculator import calculate_exposure
from app.modules.exposure.interfaces import PositionValue

PORTFOLIO_ID = uuid4()


def _pv(
    iid: str,
    mv: Decimal,
    *,
    sector: str = "Technology",
    country: str = "US",
    currency: str = "USD",
    asset_class: str = "equity",
) -> PositionValue:
    qty = Decimal("100") if mv >= 0 else Decimal("-100")
    price = abs(mv) / abs(qty)
    return PositionValue(
        instrument_id=iid,
        quantity=qty,
        market_price=price,
        market_value=mv,
        sector=sector,
        country=country,
        currency=currency,
        asset_class=asset_class,
    )


# ---------------------------------------------------------------------------
# Gross / net exposure
# ---------------------------------------------------------------------------


class TestGrossNetExposure:
    def test_all_long(self):
        positions = [
            _pv("AAPL", Decimal("500000")),
            _pv("MSFT", Decimal("300000")),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        assert result.gross_exposure == Decimal("800000")
        assert result.net_exposure == Decimal("800000")
        assert result.long_exposure == Decimal("800000")
        assert result.short_exposure == Decimal("0")
        assert result.long_count == 2
        assert result.short_count == 0

    def test_long_short(self):
        positions = [
            _pv("AAPL", Decimal("600000")),
            _pv("TSLA", Decimal("-200000")),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        assert result.gross_exposure == Decimal("800000")
        assert result.net_exposure == Decimal("400000")
        assert result.long_exposure == Decimal("600000")
        assert result.short_exposure == Decimal("-200000")
        assert result.long_count == 1
        assert result.short_count == 1

    def test_empty_portfolio(self):
        result = calculate_exposure(PORTFOLIO_ID, [])
        assert result.gross_exposure == Decimal("0")
        assert result.net_exposure == Decimal("0")
        assert result.long_count == 0
        assert result.short_count == 0


# ---------------------------------------------------------------------------
# Sector breakdown
# ---------------------------------------------------------------------------


class TestSectorBreakdown:
    def test_sector_weights_sum_to_100(self):
        positions = [
            _pv("AAPL", Decimal("600000"), sector="Technology"),
            _pv("JNJ", Decimal("400000"), sector="Healthcare"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        sector_bd = result.breakdowns.get("sector", [])
        total_weight = sum(bd.weight_pct for bd in sector_bd)
        assert total_weight == pytest.approx(Decimal("100"), abs=Decimal("0.01"))

    def test_correct_sector_values(self):
        positions = [
            _pv("AAPL", Decimal("600000"), sector="Technology"),
            _pv("MSFT", Decimal("200000"), sector="Technology"),
            _pv("JNJ", Decimal("200000"), sector="Healthcare"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        sector_bd = {bd.key: bd for bd in result.breakdowns.get("sector", [])}
        assert sector_bd["Technology"].gross_value == Decimal("800000")
        assert sector_bd["Healthcare"].gross_value == Decimal("200000")
        assert sector_bd["Technology"].weight_pct == Decimal("80")


# ---------------------------------------------------------------------------
# Country breakdown
# ---------------------------------------------------------------------------


class TestCountryBreakdown:
    def test_country_breakdown(self):
        positions = [
            _pv("AAPL", Decimal("500000"), country="US"),
            _pv("7203.T", Decimal("300000"), country="JP"),
            _pv("VOD.L", Decimal("200000"), country="GB"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        country_bd = {bd.key: bd for bd in result.breakdowns.get("country", [])}
        assert country_bd["US"].gross_value == Decimal("500000")
        assert country_bd["JP"].gross_value == Decimal("300000")
        assert country_bd["GB"].gross_value == Decimal("200000")


# ---------------------------------------------------------------------------
# Mixed long/short breakdown
# ---------------------------------------------------------------------------


class TestMixedBreakdown:
    def test_sector_long_short_split(self):
        positions = [
            _pv("AAPL", Decimal("600000"), sector="Technology"),
            _pv("TSLA", Decimal("-200000"), sector="Technology"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        sector_bd = {bd.key: bd for bd in result.breakdowns.get("sector", [])}
        tech = sector_bd["Technology"]
        assert tech.long_value == Decimal("600000")
        assert tech.short_value == Decimal("-200000")
        assert tech.net_value == Decimal("400000")
        assert tech.gross_value == Decimal("800000")


# ---------------------------------------------------------------------------
# Currency / asset class dimensions
# ---------------------------------------------------------------------------


class TestOtherDimensions:
    def test_currency_breakdown(self):
        positions = [
            _pv("AAPL", Decimal("500000"), currency="USD"),
            _pv("VOD.L", Decimal("300000"), currency="GBP"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        curr_bd = {bd.key: bd for bd in result.breakdowns.get("currency", [])}
        assert "USD" in curr_bd
        assert "GBP" in curr_bd

    def test_asset_class_breakdown(self):
        positions = [
            _pv("AAPL", Decimal("500000"), asset_class="equity"),
            _pv("UST10Y", Decimal("300000"), asset_class="fixed_income"),
        ]
        result = calculate_exposure(PORTFOLIO_ID, positions)
        ac_bd = {bd.key: bd for bd in result.breakdowns.get("asset_class", [])}
        assert "equity" in ac_bd
        assert "fixed_income" in ac_bd
