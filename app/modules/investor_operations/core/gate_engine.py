"""Gate engine — pro-rates redemption requests when total exceeds fund-level threshold.

Pure functions, no I/O.  The gate percentage is expressed as a fraction of
fund NAV (e.g. 0.25 = investors can redeem up to 25% of NAV in one period).
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from app.modules.investor_operations.interfaces import GateAllocation, GateCheckResult


def check_gate(
    requests: list[tuple[str, Decimal]],
    fund_nav: Decimal,
    gate_pct: Decimal,
) -> GateCheckResult:
    """Apply the fund-level redemption gate to a batch of requests.

    Parameters
    ----------
    requests:
        List of ``(request_id, requested_amount)`` tuples.
    fund_nav:
        Current fund NAV used to compute gate capacity.
    gate_pct:
        Maximum fraction of NAV redeemable in one period (e.g. ``Decimal("0.25")``).

    Returns
    -------
    GateCheckResult with per-request allocations.  If total requested is
    within the gate, every request gets its full amount.  Otherwise amounts
    are pro-rated proportionally, with rounding remainder assigned to the
    last request (same pattern as PnL allocation).
    """
    if not requests:
        return GateCheckResult(
            gate_triggered=False,
            total_requested=Decimal(0),
            total_approved=Decimal(0),
            gate_capacity=fund_nav * gate_pct,
            allocations=[],
        )

    gate_capacity = fund_nav * gate_pct
    total_requested = sum(amt for _, amt in requests)

    if total_requested <= gate_capacity:
        return GateCheckResult(
            gate_triggered=False,
            total_requested=total_requested,
            total_approved=total_requested,
            gate_capacity=gate_capacity,
            allocations=[
                GateAllocation(
                    request_id=UUID(rid),
                    original_amount=amt,
                    approved_amount=amt,
                    proration_pct=Decimal(1),
                )
                for rid, amt in requests
            ],
        )

    # Pro-rate proportionally
    allocations: list[GateAllocation] = []
    allocated_so_far = Decimal(0)

    for i, (rid, amt) in enumerate(requests):
        is_last = i == len(requests) - 1
        proration_pct = (amt / total_requested).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)

        if is_last:
            # Last investor gets the remainder to avoid rounding drift
            approved = gate_capacity - allocated_so_far
        else:
            approved = (gate_capacity * amt / total_requested).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            allocated_so_far += approved

        allocations.append(
            GateAllocation(
                request_id=UUID(rid),
                original_amount=amt,
                approved_amount=approved,
                proration_pct=proration_pct,
            )
        )

    return GateCheckResult(
        gate_triggered=True,
        total_requested=total_requested,
        total_approved=gate_capacity,
        gate_capacity=gate_capacity,
        allocations=allocations,
    )
