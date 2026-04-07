"""Fund administrator simulation — independent position/NAV/cash computation.

A real fund administrator (Citco, SS&C, NAV Consulting) independently tracks
positions, NAV, and cash from trade confirmations and corporate actions.  The
administrator's numbers are compared against the fund's internal books and the
prime broker's records in the daily three-way reconciliation.

This service simulates the administrator by independently aggregating fills
from the execution engine, with occasional deliberate mismatches to exercise
the reconciliation break detection path.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from mock_exchange.execution.engine import ExecutionEngine

logger = structlog.get_logger()

ZERO = Decimal(0)

# Probability of introducing a deliberate mismatch per position
_MISMATCH_PROBABILITY = 0.05


class FundAdminService:
    """Simulates an independent fund administrator's view of the fund."""

    def __init__(self, execution_engine: ExecutionEngine) -> None:
        self._engine = execution_engine

    def get_positions(self) -> dict[str, Decimal]:
        """Compute positions from fills, with occasional deliberate mismatches.

        The admin independently aggregates filled orders — same source data as
        the broker, but computed separately. Rare mismatches simulate real-world
        discrepancies (late trade bookings, corporate action timing, etc.).
        """
        positions: dict[str, Decimal] = {}
        for order in self._engine.get_all_orders():
            if order.status not in ("filled", "partially_filled"):
                continue
            qty = order.filled_quantity
            if order.side == "sell":
                qty = -qty
            positions[order.instrument_id] = positions.get(
                order.instrument_id, ZERO
            ) + qty

        # Introduce deliberate mismatches for realism
        for iid in list(positions):
            if random.random() < _MISMATCH_PROBABILITY:
                adj = Decimal(random.choice([-1, 1])) * Decimal(
                    random.randint(1, 5)
                )
                positions[iid] += adj
                logger.debug(
                    "admin_deliberate_mismatch",
                    instrument_id=iid,
                    adjustment=str(adj),
                )

        return positions

    def get_cash_balances(self) -> dict[str, Decimal]:
        """Compute cash balances from fills.

        Simplified: sum of -(qty * price) for buys, +(qty * price) for sells,
        grouped by currency (USD only for now).
        """
        cash: dict[str, Decimal] = {"USD": ZERO}
        for order in self._engine.get_all_orders():
            if order.status not in ("filled", "partially_filled"):
                continue
            if order.avg_fill_price is None:
                continue
            amount = order.filled_quantity * order.avg_fill_price
            if order.side == "buy":
                cash["USD"] -= amount
            else:
                cash["USD"] += amount

        return cash

    def get_nav(self, prices: dict[str, Decimal]) -> Decimal:
        """Compute NAV = sum(position_qty * price) + cash.

        Uses provided price map for mark-to-market.
        """
        positions = self.get_positions()
        cash = self.get_cash_balances()

        market_value = sum(
            qty * prices.get(iid, ZERO) for iid, qty in positions.items()
        )
        total_cash = sum(cash.values())

        return market_value + total_cash
