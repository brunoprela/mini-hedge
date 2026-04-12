"""Unit tests for capital accounts calculator — pure allocation math."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.capital_accounts.core.calculator import (
    allocate_fees,
    allocate_pnl,
    compute_redemption_shares,
    compute_subscription_shares,
    recompute_ownership,
)

ZERO = Decimal("0")


class TestAllocatePnl:
    def test_single_investor_gets_full_pnl(self) -> None:
        accounts = [("a1", Decimal("1000000"), Decimal("1.0"))]
        result = allocate_pnl(accounts, Decimal("50000"))
        assert len(result) == 1
        aid, pnl, new_cap = result[0]
        assert pnl == Decimal("50000")
        assert new_cap == Decimal("1050000")

    def test_two_investors_proportional(self) -> None:
        accounts = [
            ("a1", Decimal("600000"), Decimal("0.6")),
            ("a2", Decimal("400000"), Decimal("0.4")),
        ]
        result = allocate_pnl(accounts, Decimal("10000"))
        pnl_map = {aid: pnl for aid, pnl, _ in result}
        assert pnl_map["a1"] == Decimal("6000.00")
        # a2 gets remainder
        assert pnl_map["a2"] == Decimal("4000.00")

    def test_negative_pnl(self) -> None:
        accounts = [("a1", Decimal("500000"), Decimal("1.0"))]
        result = allocate_pnl(accounts, Decimal("-20000"))
        _, pnl, new_cap = result[0]
        assert pnl == Decimal("-20000")
        assert new_cap == Decimal("480000")

    def test_zero_pnl_no_change(self) -> None:
        accounts = [("a1", Decimal("500000"), Decimal("1.0"))]
        result = allocate_pnl(accounts, ZERO)
        _, pnl, new_cap = result[0]
        assert pnl == ZERO
        assert new_cap == Decimal("500000")

    def test_empty_accounts(self) -> None:
        assert allocate_pnl([], Decimal("10000")) == []

    def test_zero_ownership(self) -> None:
        accounts = [("a1", Decimal("500000"), ZERO)]
        result = allocate_pnl(accounts, Decimal("10000"))
        _, pnl, _ = result[0]
        assert pnl == ZERO

    def test_three_investors_remainder_to_last(self) -> None:
        accounts = [
            ("a1", Decimal("333333"), Decimal("0.333333")),
            ("a2", Decimal("333333"), Decimal("0.333333")),
            ("a3", Decimal("333334"), Decimal("0.333334")),
        ]
        result = allocate_pnl(accounts, Decimal("100"))
        total_pnl = sum(pnl for _, pnl, _ in result)
        assert total_pnl == Decimal("100")


class TestAllocateFees:
    def test_single_investor_pays_full_fee(self) -> None:
        accounts = [("a1", Decimal("1000000"), Decimal("1.0"))]
        result = allocate_fees(accounts, Decimal("5000"))
        aid, fee, new_cap = result[0]
        assert fee == Decimal("5000")
        assert new_cap == Decimal("995000")

    def test_fee_deducted(self) -> None:
        accounts = [("a1", Decimal("100000"), Decimal("1.0"))]
        result = allocate_fees(accounts, Decimal("500"))
        _, _, new_cap = result[0]
        assert new_cap == Decimal("99500")

    def test_zero_fee(self) -> None:
        accounts = [("a1", Decimal("100000"), Decimal("1.0"))]
        result = allocate_fees(accounts, ZERO)
        _, fee, new_cap = result[0]
        assert fee == ZERO
        assert new_cap == Decimal("100000")

    def test_zero_ownership_returns_zero_fee(self) -> None:
        """When total_pct is zero, no fees are allocated."""
        accounts = [("a1", Decimal("100000"), ZERO)]
        result = allocate_fees(accounts, Decimal("500"))
        _, fee, new_cap = result[0]
        assert fee == ZERO
        assert new_cap == Decimal("100000")

    def test_two_investors_proportional_fees(self) -> None:
        accounts = [
            ("a1", Decimal("750000"), Decimal("0.75")),
            ("a2", Decimal("250000"), Decimal("0.25")),
        ]
        result = allocate_fees(accounts, Decimal("1000"))
        fee_map = {aid: fee for aid, fee, _ in result}
        assert fee_map["a1"] == Decimal("750.00")
        assert fee_map["a2"] == Decimal("250.00")


class TestRecomputeOwnership:
    def test_single_investor_100_pct(self) -> None:
        result = recompute_ownership([("a1", Decimal("1000000"))])
        assert result[0] == ("a1", Decimal("1"))

    def test_two_equal_investors(self) -> None:
        accounts = [("a1", Decimal("500000")), ("a2", Decimal("500000"))]
        result = recompute_ownership(accounts)
        pcts = {aid: pct for aid, pct in result}
        assert pcts["a1"] == Decimal("0.500000")
        # Last investor gets remainder to ensure sum = 1.0
        assert pcts["a2"] == Decimal("0.500000")

    def test_unequal_split(self) -> None:
        accounts = [("a1", Decimal("700000")), ("a2", Decimal("300000"))]
        result = recompute_ownership(accounts)
        pcts = {aid: pct for aid, pct in result}
        assert pcts["a1"] == Decimal("0.700000")
        total = sum(pct for _, pct in result)
        assert total == Decimal("1")

    def test_zero_total_capital_even_split(self) -> None:
        accounts = [("a1", ZERO), ("a2", ZERO)]
        result = recompute_ownership(accounts)
        assert result[0][1] == Decimal("0.500000")
        assert result[1][1] == Decimal("0.500000")

    def test_empty_accounts(self) -> None:
        assert recompute_ownership([]) == []

    def test_sum_to_one(self) -> None:
        accounts = [
            ("a1", Decimal("333333")),
            ("a2", Decimal("333333")),
            ("a3", Decimal("333334")),
        ]
        result = recompute_ownership(accounts)
        total = sum(pct for _, pct in result)
        assert total == Decimal("1")


class TestComputeSubscriptionShares:
    def test_basic_calculation(self) -> None:
        shares = compute_subscription_shares(Decimal("500000"), Decimal("100"))
        assert shares == Decimal("5000.000000")

    def test_zero_nav(self) -> None:
        shares = compute_subscription_shares(Decimal("500000"), ZERO)
        assert shares == ZERO

    def test_negative_nav(self) -> None:
        shares = compute_subscription_shares(Decimal("500000"), Decimal("-1"))
        assert shares == ZERO

    def test_fractional_shares(self) -> None:
        shares = compute_subscription_shares(Decimal("100000"), Decimal("33.33"))
        assert shares > ZERO
        # Should be quantized to 6 decimal places
        assert shares == shares.quantize(Decimal("0.000001"))


class TestComputeRedemptionShares:
    def test_basic_calculation(self) -> None:
        shares = compute_redemption_shares(Decimal("200000"), Decimal("100"))
        assert shares == Decimal("2000.000000")

    def test_zero_nav(self) -> None:
        shares = compute_redemption_shares(Decimal("200000"), ZERO)
        assert shares == ZERO
