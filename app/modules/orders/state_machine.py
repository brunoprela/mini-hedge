"""Order state machine — deterministic, pure, no I/O."""

from __future__ import annotations

from app.modules.orders.interface import OrderState


class InvalidTransitionError(Exception):
    def __init__(self, current: OrderState, target: OrderState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current} to {target}")


# Valid state transitions
_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.DRAFT: {
        OrderState.PENDING_COMPLIANCE,
        OrderState.CANCELLED,
    },
    OrderState.PENDING_COMPLIANCE: {
        OrderState.APPROVED,
        OrderState.REJECTED,
    },
    OrderState.APPROVED: {OrderState.SENT, OrderState.CANCELLED},
    OrderState.REJECTED: set(),  # terminal
    OrderState.SENT: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
    },
    OrderState.FILLED: set(),  # terminal
    OrderState.CANCELLED: set(),  # terminal
}


def get_valid_transitions(state: OrderState) -> set[OrderState]:
    return _TRANSITIONS.get(state, set())


def apply_transition(current: OrderState, target: OrderState) -> OrderState:
    valid = get_valid_transitions(current)
    if target not in valid:
        raise InvalidTransitionError(current, target)
    return target
