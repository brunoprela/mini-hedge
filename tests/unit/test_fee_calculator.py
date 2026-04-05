"""Unit tests for fee accounting calculators — pure functions, no I/O."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.fee_accounting.calculator import (
    calculate_daily_management_fee,
    calculate_performance_fee,
    should_crystallize,
)

# ---------------------------------------------------------------------------
# Management fee
# ---------------------------------------------------------------------------


class TestDailyManagementFee:
    def test_standard_2pct_on_100m(self) -> None:
        """2% (200 bps) on $100M NAV = $100M * 200/10000/365 ~ $5,479.45/day."""
        nav = Decimal("100_000_000")
        fee = calculate_daily_management_fee(nav, annual_bps=200)
        assert fee == Decimal("5479.45")

    def test_zero_nav(self) -> None:
        fee = calculate_daily_management_fee(Decimal(0), annual_bps=200)
        assert fee == Decimal(0)

    def test_zero_bps(self) -> None:
        fee = calculate_daily_management_fee(Decimal("100_000_000"), annual_bps=0)
        assert fee == Decimal(0)

    def test_small_nav(self) -> None:
        """1% (100 bps) on $1M."""
        nav = Decimal("1_000_000")
        fee = calculate_daily_management_fee(nav, annual_bps=100)
        # 1_000_000 * 100 / 10_000 / 365 = 27.397...
        assert fee == Decimal("27.40")


# ---------------------------------------------------------------------------
# Performance fee
# ---------------------------------------------------------------------------


class TestPerformanceFee:
    def test_gain_above_hwm_no_hurdle(self) -> None:
        """20% on gains above HWM. NAV=$110M, HWM=$100M, gain=$10M, fee=$2M."""
        fee = calculate_performance_fee(
            current_nav=Decimal("110_000_000"),
            hwm_nav=Decimal("100_000_000"),
            pct=Decimal("20"),
            hurdle_annual=Decimal("0"),
            days=0,
        )
        assert fee == Decimal("2_000_000.00")

    def test_no_fee_when_below_hwm(self) -> None:
        """No performance fee when NAV is below HWM."""
        fee = calculate_performance_fee(
            current_nav=Decimal("95_000_000"),
            hwm_nav=Decimal("100_000_000"),
            pct=Decimal("20"),
            hurdle_annual=Decimal("0"),
            days=0,
        )
        assert fee == Decimal(0)

    def test_no_fee_when_equal_to_hwm(self) -> None:
        fee = calculate_performance_fee(
            current_nav=Decimal("100_000_000"),
            hwm_nav=Decimal("100_000_000"),
            pct=Decimal("20"),
            hurdle_annual=Decimal("0"),
            days=0,
        )
        assert fee == Decimal(0)

    def test_with_hurdle_rate(self) -> None:
        """4% annual hurdle over 90 days reduces the fee-eligible gain.

        Hurdle-adjusted HWM = 100M * (1 + 0.04 * 90/365) = 100M * 1.009863...
                            = 100_986_301.37 (approx)
        Gain above hurdle   = 110M - 100_986_301.37 = 9_013_698.63
        Fee                 = 20% * 9_013_698.63 = 1_802_739.73
        """
        fee = calculate_performance_fee(
            current_nav=Decimal("110_000_000"),
            hwm_nav=Decimal("100_000_000"),
            pct=Decimal("20"),
            hurdle_annual=Decimal("4"),
            days=90,
        )
        # The hurdle reduces the eligible gain, so fee < $2M
        assert fee < Decimal("2_000_000")
        assert fee > Decimal("1_800_000")

    def test_hurdle_exceeds_gain(self) -> None:
        """If hurdle-adjusted HWM exceeds current NAV, no fee is charged."""
        fee = calculate_performance_fee(
            current_nav=Decimal("100_500_000"),
            hwm_nav=Decimal("100_000_000"),
            pct=Decimal("20"),
            hurdle_annual=Decimal("4"),
            days=365,
        )
        # Hurdle-adjusted HWM = 100M * 1.04 = 104M > 100.5M
        assert fee == Decimal(0)


# ---------------------------------------------------------------------------
# Crystallization schedule
# ---------------------------------------------------------------------------


class TestShouldCrystallize:
    @pytest.mark.parametrize(
        "d",
        [
            date(2026, 3, 31),
            date(2026, 6, 30),
            date(2026, 9, 30),
            date(2026, 12, 31),
        ],
    )
    def test_quarterly_end_dates(self, d: date) -> None:
        assert should_crystallize("quarterly", d) is True

    @pytest.mark.parametrize(
        "d",
        [
            date(2026, 1, 31),
            date(2026, 3, 30),
            date(2026, 4, 30),
            date(2026, 7, 15),
        ],
    )
    def test_quarterly_non_end_dates(self, d: date) -> None:
        assert should_crystallize("quarterly", d) is False

    def test_annual_dec_31(self) -> None:
        assert should_crystallize("annual", date(2026, 12, 31)) is True

    def test_annual_non_dec_31(self) -> None:
        assert should_crystallize("annual", date(2026, 6, 30)) is False
        assert should_crystallize("annual", date(2026, 12, 30)) is False

    def test_unknown_frequency(self) -> None:
        assert should_crystallize("monthly", date(2026, 1, 31)) is False
