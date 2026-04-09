"""Order state machine — deterministic, pure, no I/O."""

from __future__ import annotations

from app.modules.orders.interfaces import OrderState


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
    OrderState.APPROVED: {OrderState.SENT, OrderState.WORKING, OrderState.CANCELLED},
    OrderState.REJECTED: set(),  # terminal
    OrderState.WORKING: {  # parent algo order: actively spawning children
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
    },
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


def derive_parent_state(child_states: list[OrderState]) -> OrderState:
    """Compute parent order state from aggregate children states."""
    if not child_states:
        return OrderState.WORKING
    if all(s == OrderState.FILLED for s in child_states):
        return OrderState.FILLED
    if all(s == OrderState.CANCELLED for s in child_states):
        return OrderState.CANCELLED
    if any(s in (OrderState.FILLED, OrderState.PARTIALLY_FILLED) for s in child_states):
        return OrderState.PARTIALLY_FILLED
    return OrderState.WORKING
