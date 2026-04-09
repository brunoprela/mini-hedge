"""Unit tests for fund terms engine — pure date arithmetic and threshold checks."""

from datetime import date
from decimal import Decimal

from app.modules.investor_operations.core.fund_terms import (
    check_lock_up,
    compute_lock_up_expiry,
    compute_next_dealing_date,
    compute_notice_deadline,
    compute_payment_due_date,
    validate_minimum_amount,
)
from app.modules.investor_operations.interfaces import RedemptionFrequency


class TestComputeNextDealingDate:
    def test_monthly_last_day(self) -> None:
        result = compute_next_dealing_date(RedemptionFrequency.MONTHLY, -1, date(2026, 3, 15))
        # Last business day of March 2026 (31st is Tuesday)
        assert result == date(2026, 3, 31)

    def test_monthly_last_day_weekend_adjustment(self) -> None:
        # May 2026: 31st is Sunday → should adjust to Friday 29th
        result = compute_next_dealing_date(RedemptionFrequency.MONTHLY, -1, date(2026, 5, 1))
        assert result == date(2026, 5, 29)

    def test_monthly_specific_day(self) -> None:
        result = compute_next_dealing_date(RedemptionFrequency.MONTHLY, 15, date(2026, 3, 1))
        # March 15, 2026 is a Sunday → should adjust to Friday 13th
        assert result == date(2026, 3, 13)

    def test_monthly_past_day_rolls_to_next_month(self) -> None:
        # Already past the 15th this month
        result = compute_next_dealing_date(RedemptionFrequency.MONTHLY, 15, date(2026, 3, 20))
        # April 15, 2026 is Wednesday — valid
        assert result == date(2026, 4, 15)

    def test_quarterly(self) -> None:
        result = compute_next_dealing_date(RedemptionFrequency.QUARTERLY, -1, date(2026, 1, 15))
        # Last business day of March 2026 (31st is Tuesday)
        assert result == date(2026, 3, 31)

    def test_quarterly_after_q1_end(self) -> None:
        result = compute_next_dealing_date(RedemptionFrequency.QUARTERLY, -1, date(2026, 4, 1))
        # Last business day of June 2026 (30th is Tuesday)
        assert result == date(2026, 6, 30)

    def test_annual(self) -> None:
        result = compute_next_dealing_date(RedemptionFrequency.ANNUAL, -1, date(2026, 6, 1))
        # Last business day of December 2026 (31st is Thursday)
        assert result == date(2026, 12, 31)

    def test_result_is_always_weekday(self) -> None:
        """Dealing dates never fall on weekends."""
        for m in range(1, 13):
            result = compute_next_dealing_date(RedemptionFrequency.MONTHLY, -1, date(2026, m, 1))
            assert result.weekday() < 5, f"Month {m}: {result} is a weekend"


class TestCheckLockUp:
    def test_lock_up_not_expired(self) -> None:
        assert check_lock_up(date(2026, 1, 1), 12, date(2026, 6, 1)) is False

    def test_lock_up_expired(self) -> None:
        assert check_lock_up(date(2025, 1, 1), 12, date(2026, 2, 1)) is True

    def test_lock_up_exactly_at_expiry(self) -> None:
        assert check_lock_up(date(2025, 1, 1), 12, date(2026, 1, 1)) is True


class TestComputeLockUpExpiry:
    def test_basic(self) -> None:
        assert compute_lock_up_expiry(date(2025, 6, 15), 12) == date(2026, 6, 15)

    def test_end_of_month_clamping(self) -> None:
        # Jan 31 + 1 month = Feb 28 (2026 is not a leap year)
        assert compute_lock_up_expiry(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_leap_year(self) -> None:
        # Jan 31 + 1 month in 2028 (leap year) = Feb 29
        assert compute_lock_up_expiry(date(2028, 1, 31), 1) == date(2028, 2, 29)


class TestComputeNoticeDeadline:
    def test_45_days(self) -> None:
        assert compute_notice_deadline(date(2026, 1, 1), 45) == date(2026, 2, 15)

    def test_zero_days(self) -> None:
        assert compute_notice_deadline(date(2026, 6, 1), 0) == date(2026, 6, 1)


class TestComputePaymentDueDate:
    def test_30_days(self) -> None:
        assert compute_payment_due_date(date(2026, 3, 31), 30) == date(2026, 4, 30)


class TestValidateMinimumAmount:
    def test_above_minimum(self) -> None:
        assert validate_minimum_amount(Decimal("2000000"), Decimal("1000000")) is True

    def test_at_minimum(self) -> None:
        assert validate_minimum_amount(Decimal("1000000"), Decimal("1000000")) is True

    def test_below_minimum(self) -> None:
        assert validate_minimum_amount(Decimal("500000"), Decimal("1000000")) is False
