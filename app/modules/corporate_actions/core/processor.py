"""Pure corporate action processing functions — no I/O.

Each function takes a CorporateAction (from the adapter layer) and the
current position quantity, then returns a list of PositionAdjustments
describing the effect on the portfolio.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.corporate_actions.interfaces import ActionType, PositionAdjustment

if TYPE_CHECKING:
    from app.shared.adapters.corporate_actions import CorporateAction

logger = structlog.get_logger()

_DEFAULT_SPINOFF_ALLOCATION = Decimal("0.20")


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
        return _spinoff(action, quantity, cost_basis)
    if action_type == ActionType.MERGER:
        return _merger(action, quantity, cost_basis)

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
    ratio = action.amount if action.amount and action.amount > 0 else Decimal(1)
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
    ratio = action.amount if action.amount and action.amount > 0 else Decimal(1)
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


def _spinoff(
    action: CorporateAction,
    quantity: Decimal,
    cost_basis: Decimal,
) -> list[PositionAdjustment]:
    """Spinoff — allocate a fraction of cost basis to the new entity.

    ``action.amount`` is the cost basis allocation ratio (e.g. 0.20 means
    20% of the parent's cost basis transfers to the spun-off entity).
    The parent retains the remaining 80%.

    Two adjustments are returned:
    1. Parent instrument — reduce cost basis by the allocated fraction.
    2. Child instrument — new position with allocated cost basis.
       The child instrument_id is encoded as ``<parent>-SPINOFF`` by the
       mock exchange; a real feed would supply the actual new ticker.
    """
    ratio = action.amount or _DEFAULT_SPINOFF_ALLOCATION
    allocated_basis = cost_basis * ratio

    child_instrument_id = f"{action.instrument_id}-SPINOFF"

    return [
        # Parent: reduce cost basis, no share change
        PositionAdjustment(
            instrument_id=action.instrument_id,
            quantity_delta=Decimal(0),
            cost_basis_adjustment=-allocated_basis,
            cash_amount=Decimal(0),
        ),
        # Child: new position with same share count, allocated cost basis
        PositionAdjustment(
            instrument_id=child_instrument_id,
            quantity_delta=quantity,
            cost_basis_adjustment=allocated_basis,
            cash_amount=Decimal(0),
        ),
    ]


def _merger(
    action: CorporateAction,
    quantity: Decimal,
    cost_basis: Decimal,
) -> list[PositionAdjustment]:
    """Merger — position is closed out at the merger consideration price.

    ``action.amount`` is the cash consideration per share. The entire
    position is liquidated: shares go to zero, and the holder receives
    cash = quantity × amount.

    If the merger is stock-for-stock (no cash consideration), amount will
    be zero and no cash is credited — the acquirer shares would be
    handled as a separate corporate action from the feed.
    """
    cash_per_share = action.amount or Decimal(0)
    cash_proceeds = quantity * cash_per_share

    return [
        PositionAdjustment(
            instrument_id=action.instrument_id,
            quantity_delta=-quantity,  # close out entire position
            cost_basis_adjustment=-cost_basis,  # remove all cost basis
            cash_amount=cash_proceeds,
        ),
    ]
