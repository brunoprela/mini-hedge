"""Capital accounts calculator — pure functions for allocation math.

All functions are stateless: given inputs, produce outputs.
No I/O, no database, no side effects.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
_TWO_PLACES = Decimal("0.01")
_SIX_PLACES = Decimal("0.000001")


def allocate_pnl(
    accounts: list[tuple[str, Decimal, Decimal]],
    fund_pnl: Decimal,
) -> list[tuple[str, Decimal, Decimal]]:
    """Distribute fund P&L across investors proportional to ownership.

    Args:
        accounts: List of (account_id, ending_capital, ownership_pct).
        fund_pnl: Total fund P&L to distribute (can be negative).

    Returns:
        List of (account_id, allocated_pnl, new_ending_capital).
    """
    if not accounts or fund_pnl == ZERO:
        return [(aid, ZERO, cap) for aid, cap, _ in accounts]

    total_pct = sum(pct for _, _, pct in accounts)
    if total_pct == ZERO:
        return [(aid, ZERO, cap) for aid, cap, _ in accounts]

    results: list[tuple[str, Decimal, Decimal]] = []
    allocated_so_far = ZERO

    for i, (aid, capital, pct) in enumerate(accounts):
        if i == len(accounts) - 1:
            # Last investor gets remainder to avoid rounding drift
            alloc = fund_pnl - allocated_so_far
        else:
            alloc = (fund_pnl * pct / total_pct).quantize(_TWO_PLACES, ROUND_HALF_UP)
            allocated_so_far += alloc

        new_capital = capital + alloc
        results.append((aid, alloc, new_capital))

    return results


def allocate_fees(
    accounts: list[tuple[str, Decimal, Decimal]],
    total_fee: Decimal,
) -> list[tuple[str, Decimal, Decimal]]:
    """Distribute fees across investors proportional to ownership.

    Fees are deducted (subtracted) from capital.

    Args:
        accounts: List of (account_id, ending_capital, ownership_pct).
        total_fee: Total fee amount to distribute (positive number).

    Returns:
        List of (account_id, fee_allocated, new_ending_capital).
    """
    if not accounts or total_fee == ZERO:
        return [(aid, ZERO, cap) for aid, cap, _ in accounts]

    total_pct = sum(pct for _, _, pct in accounts)
    if total_pct == ZERO:
        return [(aid, ZERO, cap) for aid, cap, _ in accounts]

    results: list[tuple[str, Decimal, Decimal]] = []
    allocated_so_far = ZERO

    for i, (aid, capital, pct) in enumerate(accounts):
        if i == len(accounts) - 1:
            fee_alloc = total_fee - allocated_so_far
        else:
            fee_alloc = (total_fee * pct / total_pct).quantize(_TWO_PLACES, ROUND_HALF_UP)
            allocated_so_far += fee_alloc

        new_capital = capital - fee_alloc
        results.append((aid, fee_alloc, new_capital))

    return results


def recompute_ownership(
    accounts: list[tuple[str, Decimal]],
) -> list[tuple[str, Decimal]]:
    """Recalculate ownership percentages from ending capital.

    Args:
        accounts: List of (account_id, ending_capital).

    Returns:
        List of (account_id, ownership_pct) where pct sums to 1.0.
    """
    total = sum(cap for _, cap in accounts)
    if total <= ZERO:
        n = len(accounts)
        if n == 0:
            return []
        even = (Decimal(1) / n).quantize(_SIX_PLACES, ROUND_HALF_UP)
        return [(aid, even) for aid, _ in accounts]

    results: list[tuple[str, Decimal]] = []
    assigned = ZERO
    for i, (aid, cap) in enumerate(accounts):
        if i == len(accounts) - 1:
            pct = Decimal(1) - assigned
        else:
            pct = (cap / total).quantize(_SIX_PLACES, ROUND_HALF_UP)
            assigned += pct
        results.append((aid, pct))

    return results


def compute_subscription_shares(
    amount: Decimal,
    nav_per_share: Decimal,
) -> Decimal:
    """Calculate shares issued for a subscription at current NAV per share."""
    if nav_per_share <= ZERO:
        return ZERO
    return (amount / nav_per_share).quantize(_SIX_PLACES, ROUND_HALF_UP)


def compute_redemption_shares(
    amount: Decimal,
    nav_per_share: Decimal,
) -> Decimal:
    """Calculate shares redeemed for a withdrawal at current NAV per share."""
    if nav_per_share <= ZERO:
        return ZERO
    return (amount / nav_per_share).quantize(_SIX_PLACES, ROUND_HALF_UP)
