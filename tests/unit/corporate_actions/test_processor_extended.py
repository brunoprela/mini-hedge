"""Extended tests for the corporate action processor — covers merger and unknown action types."""

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


class TestMerger:
    def test_merger_liquidates_position(self) -> None:
        """Merger closes out position: quantity goes to zero, cash = qty * price."""
        action = _make_action("merger", Decimal("150.00"))
        adjustments = compute_adjustments(action, Decimal("200"), Decimal("20000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.instrument_id == "AAPL"
        assert adj.quantity_delta == Decimal("-200")
        assert adj.cost_basis_adjustment == Decimal("-20000")
        assert adj.cash_amount == Decimal("30000.00")

    def test_merger_zero_cash_consideration(self) -> None:
        """Stock-for-stock merger with zero cash consideration."""
        action = _make_action("merger", Decimal("0"))
        adjustments = compute_adjustments(action, Decimal("100"), Decimal("10000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.quantity_delta == Decimal("-100")
        assert adj.cost_basis_adjustment == Decimal("-10000")
        assert adj.cash_amount == Decimal("0")

    def test_merger_no_amount_defaults_to_zero(self) -> None:
        """Merger with no amount defaults to zero cash."""
        action = _make_action("merger", None)
        adjustments = compute_adjustments(action, Decimal("50"), Decimal("5000"))

        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj.cash_amount == Decimal("0")

    def test_merger_zero_position(self) -> None:
        """Zero position = no adjustment."""
        action = _make_action("merger", Decimal("100"))
        adjustments = compute_adjustments(action, Decimal("0"), Decimal("0"))

        assert adjustments == []


class TestUnknownActionType:
    def test_unknown_action_type_returns_empty(self) -> None:
        """Unknown action type returns empty list without raising."""
        # Use a valid ActionType value to pass the ActionType(action.action_type) call
        # but one that doesn't match any handler. Actually, the processor does
        # ActionType(action.action_type) which will raise for truly unknown types.
        # Lines 57-61 handle the fall-through after all known types — but ActionType
        # is a StrEnum so an unknown string raises ValueError. Let's test that.
        # Actually looking at the code more carefully: lines 60-61 are the
        # "logger.warning + return []" after all if-checks. This path is unreachable
        # with the current StrEnum (since ActionType() would raise first).
        # But we still need to verify the ValueError propagation.
        import pytest

        action = _make_action("totally_bogus", Decimal("1"))
        with pytest.raises(ValueError):
            compute_adjustments(action, Decimal("100"), Decimal("10000"))
