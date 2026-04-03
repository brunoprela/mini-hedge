"""Unit tests for order state machine transitions."""

import pytest

from app.modules.orders.interface import OrderState
from app.modules.orders.state_machine import (
    InvalidTransitionError,
    apply_transition,
    get_valid_transitions,
)


class TestOrderStateMachine:
    def test_draft_to_pending_compliance(self) -> None:
        result = apply_transition(OrderState.DRAFT, OrderState.PENDING_COMPLIANCE)
        assert result == OrderState.PENDING_COMPLIANCE

    def test_draft_to_cancelled(self) -> None:
        result = apply_transition(OrderState.DRAFT, OrderState.CANCELLED)
        assert result == OrderState.CANCELLED

    def test_pending_to_approved(self) -> None:
        result = apply_transition(OrderState.PENDING_COMPLIANCE, OrderState.APPROVED)
        assert result == OrderState.APPROVED

    def test_pending_to_rejected(self) -> None:
        result = apply_transition(OrderState.PENDING_COMPLIANCE, OrderState.REJECTED)
        assert result == OrderState.REJECTED

    def test_approved_to_sent(self) -> None:
        result = apply_transition(OrderState.APPROVED, OrderState.SENT)
        assert result == OrderState.SENT

    def test_sent_to_filled(self) -> None:
        result = apply_transition(OrderState.SENT, OrderState.FILLED)
        assert result == OrderState.FILLED

    def test_sent_to_partially_filled(self) -> None:
        result = apply_transition(OrderState.SENT, OrderState.PARTIALLY_FILLED)
        assert result == OrderState.PARTIALLY_FILLED

    def test_partial_to_filled(self) -> None:
        result = apply_transition(OrderState.PARTIALLY_FILLED, OrderState.FILLED)
        assert result == OrderState.FILLED

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in [OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED]:
            assert get_valid_transitions(state) == set()

    def test_invalid_transition_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_transition(OrderState.FILLED, OrderState.DRAFT)

    def test_invalid_transition_rejected_to_approved(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_transition(OrderState.REJECTED, OrderState.APPROVED)

    def test_draft_cannot_skip_to_sent(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_transition(OrderState.DRAFT, OrderState.SENT)
