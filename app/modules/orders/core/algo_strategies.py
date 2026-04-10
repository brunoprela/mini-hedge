"""Algo execution strategies — pure functions that compute child order slices.

Each strategy takes a total quantity and algo parameters and returns a list
of ChildSlice objects describing when and how much to submit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.modules.orders.interfaces import AlgoParams

ZERO = Decimal(0)
ONE = Decimal(1)


@dataclass(frozen=True)
class ChildSlice:
    """A single child order to be submitted by the algo runner."""

    quantity: Decimal
    delay_seconds: float  # seconds from algo start
    limit_price: Decimal | None = None


class SliceStrategy(Protocol):
    """Protocol for algo slicing strategies."""

    def compute_slices(
        self,
        total_qty: Decimal,
        params: AlgoParams,
    ) -> list[ChildSlice]: ...


class TWAPStrategy:
    """Time-Weighted Average Price — split evenly across time window.

    Simple, predictable, used when urgency is low. Each slice gets the
    same quantity and is evenly spaced across the duration.
    """

    def compute_slices(
        self,
        total_qty: Decimal,
        params: AlgoParams,
    ) -> list[ChildSlice]:
        n = max(1, params.num_slices)
        interval = params.duration_seconds / n
        base_qty = (total_qty / n).quantize(Decimal("0.00000001"))

        slices: list[ChildSlice] = []
        allocated = ZERO
        for i in range(n):
            qty = total_qty - allocated if i == n - 1 else base_qty
            allocated += qty
            slices.append(
                ChildSlice(
                    quantity=qty,
                    delay_seconds=interval * i,
                )
            )
        return slices


class VWAPStrategy:
    """Volume-Weighted Average Price — split proportional to volume profile.

    Heavier participation during historically high-volume periods. If no
    volume profile is provided, falls back to TWAP.
    """

    def compute_slices(
        self,
        total_qty: Decimal,
        params: AlgoParams,
    ) -> list[ChildSlice]:
        profile = params.volume_profile
        if not profile:
            return TWAPStrategy().compute_slices(total_qty, params)

        n = len(profile)
        interval = params.duration_seconds / n

        # Normalize weights
        total_weight = sum(profile)
        if total_weight == ZERO:
            return TWAPStrategy().compute_slices(total_qty, params)

        slices: list[ChildSlice] = []
        allocated = ZERO
        for i, weight in enumerate(profile):
            if i == n - 1:
                qty = total_qty - allocated
            else:
                pct = weight / total_weight
                qty = (total_qty * pct).quantize(Decimal("0.00000001"))
            allocated += qty
            if qty > ZERO:
                slices.append(
                    ChildSlice(
                        quantity=qty,
                        delay_seconds=interval * i,
                    )
                )
        return slices


class IcebergStrategy:
    """Iceberg — show only a visible quantity, replenish on fill.

    Unlike TWAP/VWAP which are time-driven, Iceberg is fill-driven.
    The slices are generated upfront but the runner submits each only
    after the previous one fills (delay_seconds=0 means "on previous fill").
    """

    def compute_slices(
        self,
        total_qty: Decimal,
        params: AlgoParams,
    ) -> list[ChildSlice]:
        visible = params.visible_quantity
        if visible is None or visible <= ZERO:
            visible = (total_qty / 10).quantize(Decimal("0.00000001"))

        slices: list[ChildSlice] = []
        remaining = total_qty
        while remaining > ZERO:
            qty = min(visible, remaining)
            slices.append(
                ChildSlice(
                    quantity=qty,
                    delay_seconds=0,  # fill-triggered, not time-triggered
                )
            )
            remaining -= qty
        return slices


STRATEGY_REGISTRY: dict[str, SliceStrategy] = {
    "twap": TWAPStrategy(),
    "vwap": VWAPStrategy(),
    "iceberg": IcebergStrategy(),
}


def get_strategy(algo_type: str) -> SliceStrategy:
    strategy = STRATEGY_REGISTRY.get(algo_type)
    if strategy is None:
        msg = f"Unknown algo type: {algo_type!r}. Available: {sorted(STRATEGY_REGISTRY)}"
        raise ValueError(msg)
    return strategy
