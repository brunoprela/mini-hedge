"""Unit tests for FXConverter — in-memory rate cache with triangulation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.market_data.core.fx import FXConverter


class TestUpdateAndDirectLookup:
    def test_direct_rate(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        assert fx.get_rate("USD", "EUR") == Decimal("0.9230")

    def test_same_currency_returns_one(self) -> None:
        fx = FXConverter()
        assert fx.get_rate("USD", "USD") == Decimal(1)

    def test_inverse_rate(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "GBP", Decimal("0.8000"))
        rate = fx.get_rate("GBP", "USD")
        assert rate is not None
        assert rate == Decimal(1) / Decimal("0.8000")

    def test_unknown_pair_returns_none(self) -> None:
        fx = FXConverter()
        assert fx.get_rate("ZAR", "BRL") is None

    def test_update_overwrites_previous(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "EUR", Decimal("0.9000"))
        fx.update_rate("USD", "EUR", Decimal("0.9500"))
        assert fx.get_rate("USD", "EUR") == Decimal("0.9500")


class TestTriangulation:
    def test_cross_rate_via_usd(self) -> None:
        """GBP → EUR via USD: GBP→USD then USD→EUR."""
        fx = FXConverter()
        fx.update_rate("USD", "GBP", Decimal("0.8000"))
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        rate = fx.get_rate("GBP", "EUR")
        assert rate is not None
        # GBP→USD = 1/0.8 = 1.25, then USD→EUR = 0.923
        # GBP→EUR = 1.25 * 0.923 = 1.15375
        expected = (Decimal(1) / Decimal("0.8000")) * Decimal("0.9230")
        assert rate == expected

    def test_triangulation_both_directions(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "JPY", Decimal("151.50"))
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        # EUR → JPY
        eur_jpy = fx.get_rate("EUR", "JPY")
        # JPY → EUR
        jpy_eur = fx.get_rate("JPY", "EUR")
        assert eur_jpy is not None
        assert jpy_eur is not None
        # They should be inverses
        product = eur_jpy * jpy_eur
        assert abs(product - Decimal(1)) < Decimal("0.0001")

    def test_triangulation_fails_without_usd_leg(self) -> None:
        fx = FXConverter()
        fx.update_rate("EUR", "GBP", Decimal("0.8585"))
        # No USD rates — can't triangulate CHF→JPY
        assert fx.get_rate("CHF", "JPY") is None


class TestConvert:
    def test_basic_conversion(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        result = fx.convert(Decimal("1000"), "USD", "EUR")
        assert result == Decimal("923.0")

    def test_convert_same_currency(self) -> None:
        fx = FXConverter()
        result = fx.convert(Decimal("500"), "USD", "USD")
        assert result == Decimal("500")

    def test_convert_returns_none_when_no_rate(self) -> None:
        fx = FXConverter()
        result = fx.convert(Decimal("1000"), "ZAR", "BRL")
        assert result is None

    def test_convert_with_inverse(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "GBP", Decimal("0.8000"))
        result = fx.convert(Decimal("800"), "GBP", "USD")
        assert result is not None
        # 800 GBP * (1/0.8) = 1000 USD
        assert result == Decimal("1000.000")

    def test_convert_zero_amount(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        result = fx.convert(Decimal("0"), "USD", "EUR")
        assert result == Decimal("0")


class TestAvailablePairs:
    def test_lists_all_pairs(self) -> None:
        fx = FXConverter()
        fx.update_rate("USD", "EUR", Decimal("0.9230"))
        fx.update_rate("USD", "GBP", Decimal("0.8000"))
        pairs = fx.available_pairs
        assert pairs == ["USD/EUR", "USD/GBP"]

    def test_empty_when_no_rates(self) -> None:
        fx = FXConverter()
        assert fx.available_pairs == []
