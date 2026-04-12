"""Extended state machine tests — derive_parent_state coverage."""

from __future__ import annotations

from app.modules.orders.core.state_machine import derive_parent_state
from app.modules.orders.interfaces import OrderState


class TestDeriveParentState:
    def test_empty_children_returns_working(self) -> None:
        assert derive_parent_state([]) == OrderState.WORKING

    def test_all_filled_returns_filled(self) -> None:
        assert derive_parent_state([OrderState.FILLED, OrderState.FILLED]) == OrderState.FILLED

    def test_all_cancelled_returns_cancelled(self) -> None:
        assert derive_parent_state([OrderState.CANCELLED, OrderState.CANCELLED]) == OrderState.CANCELLED

    def test_mixed_filled_and_sent_returns_partially_filled(self) -> None:
        result = derive_parent_state([OrderState.FILLED, OrderState.SENT])
        assert result == OrderState.PARTIALLY_FILLED

    def test_partially_filled_child_returns_partially_filled(self) -> None:
        result = derive_parent_state([OrderState.PARTIALLY_FILLED, OrderState.SENT])
        assert result == OrderState.PARTIALLY_FILLED

    def test_all_sent_returns_working(self) -> None:
        result = derive_parent_state([OrderState.SENT, OrderState.SENT])
        assert result == OrderState.WORKING

    def test_mixed_cancelled_and_sent_returns_working(self) -> None:
        result = derive_parent_state([OrderState.CANCELLED, OrderState.SENT])
        assert result == OrderState.WORKING

    def test_single_filled(self) -> None:
        assert derive_parent_state([OrderState.FILLED]) == OrderState.FILLED

    def test_single_cancelled(self) -> None:
        assert derive_parent_state([OrderState.CANCELLED]) == OrderState.CANCELLED
