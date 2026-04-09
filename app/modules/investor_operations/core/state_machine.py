"""Subscription and redemption state machines — deterministic, pure, no I/O.

Follows the same pattern as ``app.modules.orders.core.state_machine``.
"""

from __future__ import annotations

from app.modules.investor_operations.interfaces import RedemptionState, SubscriptionState


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")


# ---------------------------------------------------------------------------
# Subscription transitions
# ---------------------------------------------------------------------------

_SUB_TRANSITIONS: dict[SubscriptionState, set[SubscriptionState]] = {
    SubscriptionState.DRAFT: {
        SubscriptionState.PENDING_KYC,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.PENDING_KYC: {
        SubscriptionState.KYC_APPROVED,
        SubscriptionState.KYC_REJECTED,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.KYC_APPROVED: {
        SubscriptionState.PENDING_OPS_REVIEW,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.KYC_REJECTED: set(),  # terminal
    SubscriptionState.PENDING_OPS_REVIEW: {
        SubscriptionState.PENDING_GP_APPROVAL,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.PENDING_GP_APPROVAL: {
        SubscriptionState.APPROVED,
        SubscriptionState.REJECTED,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.APPROVED: {
        SubscriptionState.PENDING_WIRE,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.REJECTED: set(),  # terminal
    SubscriptionState.PENDING_WIRE: {
        SubscriptionState.WIRE_CONFIRMED,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.WIRE_CONFIRMED: {
        SubscriptionState.QUEUED_FOR_NAV,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.QUEUED_FOR_NAV: {
        SubscriptionState.EXECUTED,
        SubscriptionState.CANCELLED,
    },
    SubscriptionState.EXECUTED: set(),  # terminal
    SubscriptionState.CANCELLED: set(),  # terminal
}


def get_valid_subscription_transitions(
    state: SubscriptionState,
) -> set[SubscriptionState]:
    return _SUB_TRANSITIONS.get(state, set())


def apply_subscription_transition(
    current: SubscriptionState,
    target: SubscriptionState,
) -> SubscriptionState:
    valid = get_valid_subscription_transitions(current)
    if target not in valid:
        raise InvalidTransitionError(current, target)
    return target


# ---------------------------------------------------------------------------
# Redemption transitions
# ---------------------------------------------------------------------------

_RED_TRANSITIONS: dict[RedemptionState, set[RedemptionState]] = {
    RedemptionState.DRAFT: {
        RedemptionState.PENDING_VALIDATION,
        RedemptionState.CANCELLED,
    },
    RedemptionState.PENDING_VALIDATION: {
        RedemptionState.VALIDATED,
        RedemptionState.VALIDATION_FAILED,
        RedemptionState.CANCELLED,
    },
    RedemptionState.VALIDATED: {
        RedemptionState.PENDING_GATE_CHECK,
        RedemptionState.CANCELLED,
    },
    RedemptionState.VALIDATION_FAILED: set(),  # terminal
    RedemptionState.PENDING_GATE_CHECK: {
        RedemptionState.GATE_APPLIED,
        RedemptionState.QUEUED_FOR_NAV,
        RedemptionState.CANCELLED,
    },
    RedemptionState.GATE_APPLIED: {
        RedemptionState.QUEUED_FOR_NAV,
        RedemptionState.CANCELLED,
    },
    RedemptionState.QUEUED_FOR_NAV: {
        RedemptionState.NAV_CALCULATED,
        RedemptionState.CANCELLED,
    },
    RedemptionState.NAV_CALCULATED: {
        RedemptionState.PENDING_PAYMENT,
        RedemptionState.CANCELLED,
    },
    RedemptionState.PENDING_PAYMENT: {
        RedemptionState.PAYMENT_SENT,
        RedemptionState.CANCELLED,
    },
    RedemptionState.PAYMENT_SENT: {
        RedemptionState.EXECUTED,
    },
    RedemptionState.EXECUTED: set(),  # terminal
    RedemptionState.CANCELLED: set(),  # terminal
}


def get_valid_redemption_transitions(
    state: RedemptionState,
) -> set[RedemptionState]:
    return _RED_TRANSITIONS.get(state, set())


def apply_redemption_transition(
    current: RedemptionState,
    target: RedemptionState,
) -> RedemptionState:
    valid = get_valid_redemption_transitions(current)
    if target not in valid:
        raise InvalidTransitionError(current, target)
    return target
