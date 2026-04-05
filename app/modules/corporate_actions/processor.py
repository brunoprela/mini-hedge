"""Pure corporate action processing functions — no I/O.

Each function takes a CorporateAction (from the adapter layer) and the
current position quantity, then returns a list of PositionAdjustments
describing the effect on the portfolio.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.corporate_actions.interface import ActionType, PositionAdjustment

if TYPE_CHECKING:
    from app.shared.adapters import CorporateAction

logger = structlog.get_logger()


def compute_adjustments(
    action: CorporateAction,
    quantity: Decimal,
    cost_basis: Decimal,
) -> list[PositionAdjustment]:
    """Compute position adjustments for a corporate action.

    Parameters
    ----------
    action:
        The corporate action event from the adapter.
    quantity:
        Current position quantity (number of shares held).
    cost_basis:
        Current total cost basis of the position.

    Returns
    -------
    list[PositionAdjustment]
        Adjustments to apply.  May be empty (e.g. zero position, spinoff).
    """
    action_type = ActionType(action.action_type)

    if quantity == Decimal(0):
        return []

    if action_type == ActionType.DIVIDEND:
        return _dividend(action, quantity)
    if action_type == ActionType.STOCK_SPLIT:
        return _stock_split(action, quantity, cost_basis)
    if action_type == ActionType.REVERSE_SPLIT:
        return _reverse_split(action, quantity, cost_basis)
    if action_type == ActionType.SPINOFF:
        return _spinoff(action)

    logger.warning("unknown_action_type", action_type=action.action_type)
    return []


def _dividend(action: CorporateAction, quantity: Decimal) -> list[PositionAdjustment]:
    """Cash dividend — credit cash, no position change."""
    dividend_amount = action.amount or Decimal(0)
    cash = quantity * dividend_amount
    return [
        PositionAdjustment(
            instrument_id=action.instrument_id,
            quantity_delta=Decimal(0),
            cost_basis_adjustment=Decimal(0),
            cash_amount=cash,
        ),
    ]


def _stock_split(
    action: CorporateAction,
    quantity: Decimal,
    cost_basis: Decimal,
) -> list[PositionAdjustment]:
    """Stock split — increase shares, reduce per-share cost basis proportionally.

    ``action.amount`` is the split ratio (e.g. 2.0 for a 2:1 split).
    """
    ratio = action.amount or Decimal(1)
    quantity_delta = quantity * (ratio - Decimal(1))
    # New total cost basis stays the same; per-share cost drops.
    # Adjustment = new_cost_basis - old_cost_basis = 0, but we express as
    # the proportional reduction: cost_basis * (1/ratio - 1).
    cost_basis_adjustment = cost_basis * (Decimal(1) / ratio - Decimal(1))
    return [
        PositionAdjustment(
            instrument_id=action.instrument_id,
            quantity_delta=quantity_delta,
            cost_basis_adjustment=cost_basis_adjustment,
            cash_amount=Decimal(0),
        ),
    ]


def _reverse_split(
    action: CorporateAction,
    quantity: Decimal,
    cost_basis: Decimal,
) -> list[PositionAdjustment]:
    """Reverse split — decrease shares, increase per-share cost basis.

    ``action.amount`` is the ratio (e.g. 3.0 for a 3:1 reverse split,
    meaning every 3 old shares become 1 new share).
    """
    ratio = action.amount or Decimal(1)
    # In a 3:1 reverse split the holder keeps quantity / ratio shares.
    quantity_delta = quantity * (Decimal(1) / ratio - Decimal(1))
    # Total cost basis unchanged; per-share cost increases by ratio.
    cost_basis_adjustment = cost_basis * (ratio - Decimal(1))
    return [
        PositionAdjustment(
            instrument_id=action.instrument_id,
            quantity_delta=quantity_delta,
            cost_basis_adjustment=cost_basis_adjustment,
            cash_amount=Decimal(0),
        ),
    ]


def _spinoff(action: CorporateAction) -> list[PositionAdjustment]:
    """Spinoff — not yet implemented; returns empty adjustments."""
    logger.info(
        "spinoff_skipped",
        action_id=action.action_id,
        instrument_id=action.instrument_id,
    )
    return []
