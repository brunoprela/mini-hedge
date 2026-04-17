"""Seed data for exposure — snapshot per portfolio with sector/country breakdowns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.exposure.models.exposure_snapshot import (
    ExposureSnapshotBreakdownRecord,
    ExposureSnapshotRecord,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository, PortfolioRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Sector breakdown templates (long_pct, short_pct)
_SECTOR_WEIGHTS: list[tuple[str, Decimal, Decimal]] = [
    ("Technology", Decimal("0.32"), Decimal("0.05")),
    ("Healthcare", Decimal("0.18"), Decimal("0.03")),
    ("Financials", Decimal("0.15"), Decimal("0.04")),
    ("Consumer Discretionary", Decimal("0.12"), Decimal("0.02")),
    ("Industrials", Decimal("0.10"), Decimal("0.01")),
    ("Energy", Decimal("0.08"), Decimal("0.03")),
    ("Communication Services", Decimal("0.05"), Decimal("0.02")),
]

_COUNTRY_WEIGHTS: list[tuple[str, Decimal, Decimal]] = [
    ("US", Decimal("0.55"), Decimal("0.10")),
    ("UK", Decimal("0.12"), Decimal("0.03")),
    ("Germany", Decimal("0.08"), Decimal("0.02")),
    ("Japan", Decimal("0.08"), Decimal("0.02")),
    ("Switzerland", Decimal("0.05"), Decimal("0.01")),
    ("France", Decimal("0.06"), Decimal("0.01")),
    ("Other", Decimal("0.06"), Decimal("0.01")),
]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for exposure snapshots."""
    exposure_service = getattr(app.state, "exposure_service", None)
    if exposure_service is None:
        logger.debug("exposure_seed_skipped", reason="service not available")
        return

    exposure_repo = exposure_service._exposure_repo
    fund_repo: FundRepository = app.state.fund_repo
    portfolio_repo: PortfolioRepository = app.state.portfolio_repo
    active_funds = await fund_repo.list_active()

    seeded = 0
    now = datetime.now(UTC)
    for fund in active_funds:
        async with sf.fund_scope(fund.slug):
            portfolios = await portfolio_repo.get_by_fund(fund.id)
            for portfolio in portfolios:
                existing = await exposure_repo.get_latest(UUID(portfolio.id))
                if existing is not None:
                    continue

                # Base NAV for scaling
                nav = Decimal("10000000")

                # Create 3 days of snapshots
                for day_offset in range(3, 0, -1):
                    snap_id = str(uuid4())
                    snap_time = now - timedelta(days=day_offset)

                    long_total = nav * Decimal("1.0")
                    short_total = nav * Decimal("0.20")

                    breakdown_rows = []
                    # Sector breakdowns
                    for sector, long_pct, short_pct in _SECTOR_WEIGHTS:
                        long_val = long_total * long_pct
                        short_val = short_total * short_pct
                        net_val = long_val - short_val
                        gross_val = long_val + short_val
                        breakdown_rows.append(
                            ExposureSnapshotBreakdownRecord(
                                id=str(uuid4()),
                                snapshot_id=snap_id,
                                dimension="sector",
                                key=sector,
                                long_value=long_val,
                                short_value=short_val,
                                net_value=net_val,
                                gross_value=gross_val,
                                weight_pct=net_val / nav,
                            )
                        )

                    # Country breakdowns
                    for country, long_pct, short_pct in _COUNTRY_WEIGHTS:
                        long_val = long_total * long_pct
                        short_val = short_total * short_pct
                        net_val = long_val - short_val
                        gross_val = long_val + short_val
                        breakdown_rows.append(
                            ExposureSnapshotBreakdownRecord(
                                id=str(uuid4()),
                                snapshot_id=snap_id,
                                dimension="country",
                                key=country,
                                long_value=long_val,
                                short_value=short_val,
                                net_value=net_val,
                                gross_value=gross_val,
                                weight_pct=net_val / nav,
                            )
                        )

                    record = ExposureSnapshotRecord(
                        id=snap_id,
                        portfolio_id=portfolio.id,
                        gross_exposure=long_total + short_total,
                        net_exposure=long_total - short_total,
                        long_exposure=long_total,
                        short_exposure=short_total,
                        long_count=25,
                        short_count=8,
                        breakdowns={},
                        snapshot_at=snap_time,
                        breakdown_rows=breakdown_rows,
                    )
                    await exposure_repo.insert_snapshot(record)
                    seeded += 1

    if seeded:
        logger.info("exposure_seed_complete", snapshots=seeded)
    else:
        logger.debug("exposure_seed_skipped", reason="data already exists")
