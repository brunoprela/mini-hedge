"""Unit tests for subscription and redemption state machine transitions."""

import pytest

from app.modules.investor_operations.core.state_machine import (
    InvalidTransitionError,
    apply_redemption_transition,
    apply_subscription_transition,
    get_valid_redemption_transitions,
    get_valid_subscription_transitions,
)
from app.modules.investor_operations.interfaces import RedemptionState, SubscriptionState


class TestSubscriptionStateMachine:
    def test_draft_to_pending_kyc(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.DRAFT, SubscriptionState.PENDING_KYC
        )
        assert result == SubscriptionState.PENDING_KYC

    def test_pending_kyc_to_approved(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.PENDING_KYC, SubscriptionState.KYC_APPROVED
        )
        assert result == SubscriptionState.KYC_APPROVED

    def test_pending_kyc_to_rejected(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.PENDING_KYC, SubscriptionState.KYC_REJECTED
        )
        assert result == SubscriptionState.KYC_REJECTED

    def test_kyc_approved_to_pending_ops(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.KYC_APPROVED, SubscriptionState.PENDING_OPS_REVIEW
        )
        assert result == SubscriptionState.PENDING_OPS_REVIEW

    def test_pending_ops_to_pending_gp(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.PENDING_OPS_REVIEW,
            SubscriptionState.PENDING_GP_APPROVAL,
        )
        assert result == SubscriptionState.PENDING_GP_APPROVAL

    def test_pending_gp_to_approved(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.PENDING_GP_APPROVAL, SubscriptionState.APPROVED
        )
        assert result == SubscriptionState.APPROVED

    def test_pending_gp_to_rejected(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.PENDING_GP_APPROVAL, SubscriptionState.REJECTED
        )
        assert result == SubscriptionState.REJECTED

    def test_approved_to_pending_wire(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.APPROVED, SubscriptionState.PENDING_WIRE
        )
        assert result == SubscriptionState.PENDING_WIRE

    def test_wire_confirmed_to_queued(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.WIRE_CONFIRMED, SubscriptionState.QUEUED_FOR_NAV
        )
        assert result == SubscriptionState.QUEUED_FOR_NAV

    def test_queued_to_executed(self) -> None:
        result = apply_subscription_transition(
            SubscriptionState.QUEUED_FOR_NAV, SubscriptionState.EXECUTED
        )
        assert result == SubscriptionState.EXECUTED

    def test_full_happy_path(self) -> None:
        """Walk through the entire subscription workflow."""
        path = [
            SubscriptionState.DRAFT,
            SubscriptionState.PENDING_KYC,
            SubscriptionState.KYC_APPROVED,
            SubscriptionState.PENDING_OPS_REVIEW,
            SubscriptionState.PENDING_GP_APPROVAL,
            SubscriptionState.APPROVED,
            SubscriptionState.PENDING_WIRE,
            SubscriptionState.WIRE_CONFIRMED,
            SubscriptionState.QUEUED_FOR_NAV,
            SubscriptionState.EXECUTED,
        ]
        for i in range(len(path) - 1):
            result = apply_subscription_transition(path[i], path[i + 1])
            assert result == path[i + 1]

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in [
            SubscriptionState.EXECUTED,
            SubscriptionState.CANCELLED,
            SubscriptionState.KYC_REJECTED,
            SubscriptionState.REJECTED,
        ]:
            assert get_valid_subscription_transitions(state) == set()

    def test_cancellation_from_any_non_terminal(self) -> None:
        non_terminal = [
            SubscriptionState.DRAFT,
            SubscriptionState.PENDING_KYC,
            SubscriptionState.KYC_APPROVED,
            SubscriptionState.PENDING_OPS_REVIEW,
            SubscriptionState.PENDING_GP_APPROVAL,
            SubscriptionState.APPROVED,
            SubscriptionState.PENDING_WIRE,
            SubscriptionState.WIRE_CONFIRMED,
            SubscriptionState.QUEUED_FOR_NAV,
        ]
        for state in non_terminal:
            result = apply_subscription_transition(state, SubscriptionState.CANCELLED)
            assert result == SubscriptionState.CANCELLED

    def test_invalid_transition_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_subscription_transition(SubscriptionState.DRAFT, SubscriptionState.EXECUTED)

    def test_cannot_transition_from_terminal(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_subscription_transition(SubscriptionState.EXECUTED, SubscriptionState.DRAFT)


class TestRedemptionStateMachine:
    def test_draft_to_pending_validation(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.DRAFT, RedemptionState.PENDING_VALIDATION
        )
        assert result == RedemptionState.PENDING_VALIDATION

    def test_pending_validation_to_validated(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.PENDING_VALIDATION, RedemptionState.VALIDATED
        )
        assert result == RedemptionState.VALIDATED

    def test_pending_validation_to_failed(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.PENDING_VALIDATION, RedemptionState.VALIDATION_FAILED
        )
        assert result == RedemptionState.VALIDATION_FAILED

    def test_validated_to_pending_gate(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.VALIDATED, RedemptionState.PENDING_GATE_CHECK
        )
        assert result == RedemptionState.PENDING_GATE_CHECK

    def test_gate_applied_to_queued(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.GATE_APPLIED, RedemptionState.QUEUED_FOR_NAV
        )
        assert result == RedemptionState.QUEUED_FOR_NAV

    def test_queued_to_nav_calculated(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.QUEUED_FOR_NAV, RedemptionState.NAV_CALCULATED
        )
        assert result == RedemptionState.NAV_CALCULATED

    def test_nav_calculated_to_pending_payment(self) -> None:
        result = apply_redemption_transition(
            RedemptionState.NAV_CALCULATED, RedemptionState.PENDING_PAYMENT
        )
        assert result == RedemptionState.PENDING_PAYMENT

    def test_payment_sent_to_executed(self) -> None:
        result = apply_redemption_transition(RedemptionState.PAYMENT_SENT, RedemptionState.EXECUTED)
        assert result == RedemptionState.EXECUTED

    def test_full_happy_path(self) -> None:
        """Walk the full redemption workflow without gate."""
        path = [
            RedemptionState.DRAFT,
            RedemptionState.PENDING_VALIDATION,
            RedemptionState.VALIDATED,
            RedemptionState.PENDING_GATE_CHECK,
            RedemptionState.QUEUED_FOR_NAV,
            RedemptionState.NAV_CALCULATED,
            RedemptionState.PENDING_PAYMENT,
            RedemptionState.PAYMENT_SENT,
            RedemptionState.EXECUTED,
        ]
        for i in range(len(path) - 1):
            result = apply_redemption_transition(path[i], path[i + 1])
            assert result == path[i + 1]

    def test_gate_applied_path(self) -> None:
        """Walk through the gate-applied variant."""
        apply_redemption_transition(
            RedemptionState.PENDING_GATE_CHECK, RedemptionState.GATE_APPLIED
        )
        apply_redemption_transition(RedemptionState.GATE_APPLIED, RedemptionState.QUEUED_FOR_NAV)

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in [
            RedemptionState.EXECUTED,
            RedemptionState.CANCELLED,
            RedemptionState.VALIDATION_FAILED,
        ]:
            assert get_valid_redemption_transitions(state) == set()

    def test_cancellation_from_non_terminal(self) -> None:
        cancellable = [
            RedemptionState.DRAFT,
            RedemptionState.PENDING_VALIDATION,
            RedemptionState.VALIDATED,
            RedemptionState.PENDING_GATE_CHECK,
            RedemptionState.GATE_APPLIED,
            RedemptionState.QUEUED_FOR_NAV,
            RedemptionState.NAV_CALCULATED,
            RedemptionState.PENDING_PAYMENT,
        ]
        for state in cancellable:
            result = apply_redemption_transition(state, RedemptionState.CANCELLED)
            assert result == RedemptionState.CANCELLED

    def test_payment_sent_cannot_cancel(self) -> None:
        """Once payment is sent, cannot cancel — only EXECUTED is valid."""
        with pytest.raises(InvalidTransitionError):
            apply_redemption_transition(RedemptionState.PAYMENT_SENT, RedemptionState.CANCELLED)

    def test_invalid_transition_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            apply_redemption_transition(RedemptionState.DRAFT, RedemptionState.EXECUTED)
