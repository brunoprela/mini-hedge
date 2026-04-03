"""Stateless exposure calculator — pure functions, no I/O."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.exposure.interface import (
    ExposureBreakdown,
    ExposureDimension,
    PortfolioExposure,
    PositionValue,
)

ZERO = Decimal(0)


def calculate_exposure(
    portfolio_id: UUID,
    positions: list[PositionValue],
) -> PortfolioExposure:
    """Calculate gross/net exposure from a list of valued positions."""
    long_total = ZERO
    short_total = ZERO
    long_count = 0
    short_count = 0

    for pv in positions:
        if pv.market_value > ZERO:
            long_total += pv.market_value
            long_count += 1
        elif pv.market_value < ZERO:
            short_total += pv.market_value
            short_count += 1

    gross = long_total + abs(short_total)
    net = long_total + short_total  # short is negative

    # Build breakdowns by each dimension
    breakdowns: dict[str, list[ExposureBreakdown]] = {}
    for dim in ExposureDimension:
        bd = _breakdown_by_dimension(dim, positions, gross)
        if bd:
            breakdowns[dim.value] = bd

    return PortfolioExposure(
        portfolio_id=portfolio_id,
        gross_exposure=gross,
        net_exposure=net,
        long_exposure=long_total,
        short_exposure=short_total,
        long_count=long_count,
        short_count=short_count,
        calculated_at=datetime.now(UTC),
        breakdowns=breakdowns,
    )


def _get_dimension_key(dim: ExposureDimension, pv: PositionValue) -> str:
    """Extract the grouping key for a dimension from a position."""
    if dim == ExposureDimension.INSTRUMENT:
        return pv.instrument_id
    elif dim == ExposureDimension.SECTOR:
        return pv.sector or "Unknown"
    elif dim == ExposureDimension.COUNTRY:
        return pv.country or "Unknown"
    elif dim == ExposureDimension.CURRENCY:
        return pv.currency
    elif dim == ExposureDimension.ASSET_CLASS:
        return pv.asset_class or "Unknown"
    return "Unknown"


def _breakdown_by_dimension(
    dim: ExposureDimension,
    positions: list[PositionValue],
    gross_total: Decimal,
) -> list[ExposureBreakdown]:
    """Group positions by dimension and compute per-group exposure."""
    longs: dict[str, Decimal] = defaultdict(lambda: ZERO)
    shorts: dict[str, Decimal] = defaultdict(lambda: ZERO)

    for pv in positions:
        key = _get_dimension_key(dim, pv)
        if pv.market_value > ZERO:
            longs[key] += pv.market_value
        elif pv.market_value < ZERO:
            shorts[key] += pv.market_value

    all_keys = set(longs.keys()) | set(shorts.keys())
    if not all_keys:
        return []

    result: list[ExposureBreakdown] = []
    for key in sorted(all_keys):
        long_val = longs.get(key, ZERO)
        short_val = shorts.get(key, ZERO)
        gross_val = long_val + abs(short_val)
        net_val = long_val + short_val
        weight = (gross_val / gross_total * 100) if gross_total else ZERO
        result.append(
            ExposureBreakdown(
                dimension=dim,
                key=key,
                long_value=long_val,
                short_value=short_val,
                net_value=net_val,
                gross_value=gross_val,
                weight_pct=weight,
            )
        )

    return result
