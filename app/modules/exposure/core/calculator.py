"""Stateless exposure calculator — pure functions, no I/O."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.exposure.core.normalizers import (
    ExposureNormalizer,
    normalize_exposure,
)
from app.modules.exposure.interfaces import (
    DimensionDrilldown,
    DrilldownItem,
    ExposureBreakdown,
    ExposureDimension,
    PortfolioExposure,
    PositionValue,
)

ZERO = Decimal(0)


def calculate_exposure(
    portfolio_id: UUID,
    positions: list[PositionValue],
    *,
    normalizers: dict[str, ExposureNormalizer] | None = None,
) -> PortfolioExposure:
    """Calculate gross/net exposure from a list of valued positions.

    When normalizers are provided, each position's exposure is computed via its
    asset-class normalizer instead of using the raw market_value.
    """
    long_total = ZERO
    short_total = ZERO
    long_count = 0
    short_count = 0

    for pv in positions:
        exposure = normalize_exposure(pv, normalizers=normalizers) if normalizers else pv.market_value
        if exposure > ZERO:
            long_total += exposure
            long_count += 1
        elif exposure < ZERO:
            short_total += exposure
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


def calculate_drilldown(
    dimension: ExposureDimension,
    key: str,
    positions: list[PositionValue],
) -> DimensionDrilldown:
    """Return per-instrument breakdown for positions matching dimension=key."""
    matching = [p for p in positions if _get_dimension_key(dimension, p) == key]
    gross_total = sum(
        (abs(p.market_value) for p in matching),
        ZERO,
    )

    items: list[DrilldownItem] = []
    for pv in matching:
        mv = pv.market_value
        long_val = mv if mv > ZERO else ZERO
        short_val = mv if mv < ZERO else ZERO
        gross_val = abs(mv)
        weight = (gross_val / gross_total * 100) if gross_total else ZERO
        items.append(
            DrilldownItem(
                instrument_id=pv.instrument_id,
                long_value=long_val,
                short_value=short_val,
                net_value=mv,
                gross_value=gross_val,
                weight_pct=weight,
            )
        )

    items.sort(key=lambda i: i.gross_value, reverse=True)
    return DimensionDrilldown(dimension=dimension.value, key=key, items=items)
