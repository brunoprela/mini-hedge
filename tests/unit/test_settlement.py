"""Unit tests for settlement date calculation."""

from datetime import date

from app.modules.cash_management.settlement import (
    calculate_settlement_date,
    get_settlement_days,
    is_business_day,
    snap_to_business_day,
)


class TestSettlementDays:
    def test_us_t_plus_1(self):
        assert get_settlement_days("US") == 1

    def test_germany_t_plus_2(self):
        assert get_settlement_days("DE") == 2

    def test_unknown_country_defaults_to_2(self):
        assert get_settlement_days("ZZ") == 2


class TestSettlementDate:
    def test_us_monday_trade(self):
        # Monday 2024-01-08 + T+1 = Tuesday 2024-01-09
        assert calculate_settlement_date(date(2024, 1, 8), "US") == date(2024, 1, 9)

    def test_us_friday_trade(self):
        # Friday 2024-01-12 + T+1 = Monday 2024-01-15 (skips weekend)
        assert calculate_settlement_date(date(2024, 1, 12), "US") == date(2024, 1, 15)

    def test_de_wednesday_trade(self):
        # Wednesday 2024-01-10 + T+2 = Friday 2024-01-12
        assert calculate_settlement_date(date(2024, 1, 10), "DE") == date(2024, 1, 12)

    def test_de_thursday_trade(self):
        # Thursday 2024-01-11 + T+2 = Monday 2024-01-15 (skips weekend)
        assert calculate_settlement_date(date(2024, 1, 11), "DE") == date(2024, 1, 15)

    def test_de_friday_trade(self):
        # Friday 2024-01-12 + T+2 = Tuesday 2024-01-16 (skips weekend)
        assert calculate_settlement_date(date(2024, 1, 12), "DE") == date(2024, 1, 16)

    def test_gb_t_plus_1(self):
        # Monday + T+1 = Tuesday
        assert calculate_settlement_date(date(2024, 1, 8), "GB") == date(2024, 1, 9)

    def test_unknown_country_t_plus_2(self):
        # Unknown country uses default T+2
        # Monday 2024-01-08 + T+2 = Wednesday 2024-01-10
        assert calculate_settlement_date(date(2024, 1, 8), "BR") == date(2024, 1, 10)


class TestSnapToBusinessDay:
    def test_monday_unchanged(self):
        assert snap_to_business_day(date(2024, 1, 8)) == date(2024, 1, 8)

    def test_friday_unchanged(self):
        assert snap_to_business_day(date(2024, 1, 12)) == date(2024, 1, 12)

    def test_saturday_snaps_to_monday(self):
        assert snap_to_business_day(date(2024, 1, 13)) == date(2024, 1, 15)

    def test_sunday_snaps_to_monday(self):
        assert snap_to_business_day(date(2024, 1, 14)) == date(2024, 1, 15)


class TestIsBusinessDay:
    def test_weekday(self):
        assert is_business_day(date(2024, 1, 8)) is True  # Monday

    def test_saturday(self):
        assert is_business_day(date(2024, 1, 13)) is False

    def test_sunday(self):
        assert is_business_day(date(2024, 1, 14)) is False
