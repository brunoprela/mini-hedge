"""Tests for the pure corporate action processor functions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.corporate_actions.core.processor import compute_adjustments
from app.shared.adapters.corporate_actions import CorporateAction


def _make_action(
    action_type: str,
    amount: Decimal | None = None,
    instrument_id: str = "AAPL",
) -> CorporateAction:
    return CorporateAction(
        action_id=f"CA-{action_type}-001",
        instrument_id=instrument_id,
        action_type=action_type,
        ex_date=date(2026, 4, 1),
        amount=amount,
    )


class TestDividend:
    def test_dividend_cash_credit(self) -> None:
        """100 shares * $2.00 dividend = $200 cash credit, no position change."""
        action = _make_action("dividend", Decimal("2.00"))
        adjustments = compute_adjustments(action, Decimal("100"), Decimal("10000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.instrument_id == "AAPL"
        assert adj.quantity_delta == Decimal("0")
        assert adj.cost_basis_adjustment == Decimal("0")
        assert adj.cash_amount == Decimal("200.00")

    def test_dividend_zero_quantity(self) -> None:
        """Zero position = no adjustment."""
        action = _make_action("dividend", Decimal("2.00"))
        adjustments = compute_adjustments(action, Decimal("0"), Decimal("0"))

        assert adjustments == []


class TestStockSplit:
    def test_two_for_one_split(self) -> None:
        """2:1 split: 100 shares becomes 200, cost basis halved."""
        action = _make_action("stock_split", Decimal("2"))
        adjustments = compute_adjustments(action, Decimal("100"), Decimal("10000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.instrument_id == "AAPL"
        # quantity_delta = 100 * (2 - 1) = 100
        assert adj.quantity_delta == Decimal("100")
        # cost_basis_adjustment = 10000 * (1/2 - 1) = -5000
        assert adj.cost_basis_adjustment == Decimal("-5000")
        assert adj.cash_amount == Decimal("0")

    def test_split_zero_quantity(self) -> None:
        """Zero position = no adjustment."""
        action = _make_action("stock_split", Decimal("2"))
        adjustments = compute_adjustments(action, Decimal("0"), Decimal("0"))

        assert adjustments == []


class TestReverseSplit:
    def test_three_for_one_reverse_split(self) -> None:
        """3:1 reverse split: 300 shares becomes 100, cost basis tripled."""
        action = _make_action("reverse_split", Decimal("3"))
        adjustments = compute_adjustments(action, Decimal("300"), Decimal("30000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.instrument_id == "AAPL"
        # quantity_delta = 300 * (1/3 - 1) = -200
        assert adj.quantity_delta == Decimal("300") * (Decimal("1") / Decimal("3") - Decimal("1"))
        # After reverse split: 100 shares, total cost basis stays 30000,
        # so per-share goes from 100 to 300 (tripled).
        # cost_basis_adjustment = 30000 * (3 - 1) = 60000
        assert adj.cost_basis_adjustment == Decimal("60000")
        assert adj.cash_amount == Decimal("0")

    def test_reverse_split_zero_quantity(self) -> None:
        """Zero position = no adjustment."""
        action = _make_action("reverse_split", Decimal("3"))
        adjustments = compute_adjustments(action, Decimal("0"), Decimal("0"))

        assert adjustments == []


class TestSpinoff:
    def test_spinoff_returns_adjustments(self) -> None:
        """Spinoff allocates a fraction of cost basis to the new child entity.

        With ratio=0.5 and cost_basis=10000:
        - Parent gets cost_basis_adjustment = -5000 (50% transferred out)
        - Child gets quantity_delta = 100 shares and cost_basis_adjustment = 5000
        """
        action = _make_action("spinoff", Decimal("0.5"))
        adjustments = compute_adjustments(action, Decimal("100"), Decimal("10000"))

        assert len(adjustments) == 2

        parent_adj = next(a for a in adjustments if a.instrument_id == "AAPL")
        child_adj = next(a for a in adjustments if a.instrument_id == "AAPL-SPINOFF")

        assert parent_adj.quantity_delta == Decimal("0")
        assert parent_adj.cost_basis_adjustment == Decimal("-5000")
        assert parent_adj.cash_amount == Decimal("0")

        assert child_adj.quantity_delta == Decimal("100")
        assert child_adj.cost_basis_adjustment == Decimal("5000")
        assert child_adj.cash_amount == Decimal("0")

    def test_spinoff_zero_quantity(self) -> None:
        """Zero position = no adjustment (before spinoff logic even runs)."""
        action = _make_action("spinoff", Decimal("0.5"))
        adjustments = compute_adjustments(action, Decimal("0"), Decimal("0"))

        assert adjustments == []
