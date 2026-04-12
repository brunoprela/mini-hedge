"""Unit tests for NettingEngine and HolidayCalendar."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.modules.cash_management.core.holiday_calendar import HolidayCalendar
from app.modules.cash_management.core.netting import NettingEngine


# ---------------------------------------------------------------------------
# Netting helpers
# ---------------------------------------------------------------------------


def _make_settlement(
    settlement_id: str = "s1",
    instrument_id: str = "AAPL",
    currency: str = "USD",
    amount: Decimal = Decimal("1000"),
) -> MagicMock:
    r = MagicMock()
    r.id = settlement_id
    r.instrument_id = instrument_id
    r.currency = currency
    r.settlement_amount = amount
    return r


# ---------------------------------------------------------------------------
# NettingEngine
# ---------------------------------------------------------------------------


class TestComputeNetting:
    def test_nets_by_counterparty_and_currency(self) -> None:
        engine = NettingEngine()
        settlements = [
            _make_settlement("s1", "AAPL", "USD", Decimal("5000")),
            _make_settlement("s2", "AAPL", "USD", Decimal("-3000")),
        ]
        cp_map = {"AAPL": "GS"}

        results = engine.compute_netting(settlements, cp_map)

        assert len(results) == 1
        assert results[0].counterparty == "GS"
        assert results[0].currency == "USD"
        assert results[0].gross_receivable == Decimal("5000")
        assert results[0].gross_payable == Decimal("3000")
        assert results[0].net_amount == Decimal("2000")
        assert results[0].settlement_count == 2

    def test_separate_buckets_for_different_currencies(self) -> None:
        engine = NettingEngine()
        settlements = [
            _make_settlement("s1", "AAPL", "USD", Decimal("1000")),
            _make_settlement("s2", "AAPL", "EUR", Decimal("500")),
        ]
        cp_map = {"AAPL": "GS"}

        results = engine.compute_netting(settlements, cp_map)

        assert len(results) == 2
        currencies = {r.currency for r in results}
        assert currencies == {"USD", "EUR"}

    def test_unknown_counterparty_uses_unknown(self) -> None:
        engine = NettingEngine()
        settlements = [_make_settlement("s1", "XYZ", "USD", Decimal("1000"))]

        results = engine.compute_netting(settlements, {})

        assert results[0].counterparty == "UNKNOWN"

    def test_empty_settlements(self) -> None:
        engine = NettingEngine()
        results = engine.compute_netting([], {})
        assert results == []

    def test_multiple_counterparties(self) -> None:
        engine = NettingEngine()
        settlements = [
            _make_settlement("s1", "AAPL", "USD", Decimal("5000")),
            _make_settlement("s2", "MSFT", "USD", Decimal("-2000")),
        ]
        cp_map = {"AAPL": "GS", "MSFT": "JPM"}

        results = engine.compute_netting(settlements, cp_map)

        assert len(results) == 2
        by_cp = {r.counterparty: r for r in results}
        assert by_cp["GS"].net_amount == Decimal("5000")
        assert by_cp["JPM"].net_amount == Decimal("-2000")


class TestComputeBilateralNetting:
    def test_bilateral_filters_and_labels(self) -> None:
        engine = NettingEngine()
        settlements = [
            _make_settlement("s1", "GS", "USD", Decimal("5000")),
            _make_settlement("s2", "GS", "USD", Decimal("-2000")),
            _make_settlement("s3", "JPM", "USD", Decimal("1000")),  # filtered out
        ]

        results = engine.compute_bilateral_netting(settlements, "US_FUND", "GS")

        assert len(results) == 1
        assert results[0].counterparty == "US_FUND<>GS"
        assert results[0].net_amount == Decimal("3000")
        assert results[0].settlement_count == 2

    def test_bilateral_no_matches(self) -> None:
        engine = NettingEngine()
        settlements = [_make_settlement("s1", "JPM", "USD", Decimal("1000"))]

        results = engine.compute_bilateral_netting(settlements, "US_FUND", "GS")

        assert results == []


# ---------------------------------------------------------------------------
# HolidayCalendar
# ---------------------------------------------------------------------------


class TestHolidayCalendar:
    def test_us_christmas_is_holiday(self) -> None:
        cal = HolidayCalendar()
        assert cal.is_holiday(date(2025, 12, 25), "US") is True

    def test_regular_weekday_not_holiday(self) -> None:
        cal = HolidayCalendar()
        # 2025-04-15 is a Tuesday, not a US holiday
        assert cal.is_holiday(date(2025, 4, 15), "US") is False

    def test_unknown_country_not_holiday(self) -> None:
        cal = HolidayCalendar()
        assert cal.is_holiday(date(2025, 12, 25), "ZZ") is False

    def test_is_business_day_weekend(self) -> None:
        cal = HolidayCalendar()
        # 2025-04-12 is a Saturday
        assert cal.is_business_day(date(2025, 4, 12), "US") is False

    def test_is_business_day_holiday(self) -> None:
        cal = HolidayCalendar()
        # 2025-07-04 is a Friday (Independence Day)
        assert cal.is_business_day(date(2025, 7, 4), "US") is False

    def test_is_business_day_normal(self) -> None:
        cal = HolidayCalendar()
        # 2025-04-14 is a Monday, not a holiday
        assert cal.is_business_day(date(2025, 4, 14), "US") is True

    def test_next_business_day_skips_weekend(self) -> None:
        cal = HolidayCalendar()
        # 2025-04-12 is Saturday → next biz day is Monday 2025-04-14
        assert cal.next_business_day(date(2025, 4, 12), "US") == date(2025, 4, 14)

    def test_next_business_day_already_biz_day(self) -> None:
        cal = HolidayCalendar()
        assert cal.next_business_day(date(2025, 4, 14), "US") == date(2025, 4, 14)

    def test_add_business_days(self) -> None:
        cal = HolidayCalendar()
        # 2025-04-11 is Friday, +2 biz days = 2025-04-15 (Tuesday)
        assert cal.add_business_days(date(2025, 4, 11), 2, "US") == date(2025, 4, 15)

    def test_add_business_days_skips_holiday(self) -> None:
        cal = HolidayCalendar()
        # 2025-07-03 is Thursday, +1 biz day should skip July 4 → Monday July 7
        assert cal.add_business_days(date(2025, 7, 3), 1, "US") == date(2025, 7, 7)

    def test_get_holidays_us(self) -> None:
        cal = HolidayCalendar()
        holidays = cal.get_holidays("US", 2025)
        assert date(2025, 12, 25) in holidays
        assert date(2025, 7, 4) in holidays
        assert len(holidays) == 8  # 8 US federal holidays

    def test_get_holidays_gb(self) -> None:
        cal = HolidayCalendar()
        holidays = cal.get_holidays("GB", 2025)
        assert date(2025, 12, 25) in holidays
        assert date(2025, 12, 26) in holidays  # Boxing Day

    def test_get_holidays_jp(self) -> None:
        cal = HolidayCalendar()
        holidays = cal.get_holidays("JP", 2025)
        assert date(2025, 1, 1) in holidays
        assert date(2025, 1, 2) in holidays

    def test_get_holidays_de(self) -> None:
        cal = HolidayCalendar()
        holidays = cal.get_holidays("DE", 2025)
        assert date(2025, 10, 3) in holidays  # German Unity Day

    def test_get_holidays_unknown_country(self) -> None:
        cal = HolidayCalendar()
        assert cal.get_holidays("ZZ", 2025) == []
