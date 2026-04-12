"""Seed data for EOD — completed run with all steps and NAV snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository, PortfolioRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# EOD step names in execution order (matches EODOrchestrator)
_STEPS = [
    "PRICE_FINALIZATION",
    "POSITION_RECONCILIATION",
    "NAV_CALCULATION",
    "PNL_SNAPSHOT",
    "FEE_ACCRUAL",
    "CAPITAL_ALLOCATION",
    "SUBSCRIPTION_EXECUTION",
    "REDEMPTION_EXECUTION",
    "RISK_SNAPSHOT",
    "ATTRIBUTION",
    "REPORT_GENERATION",
]

# NAV profiles per portfolio strategy
_NAV_PROFILES: dict[str, dict] = {
    "equity": {
        "gross_mv": Decimal("28000000"),
        "net_mv": Decimal("25000000"),
        "cash": Decimal("5000000"),
        "fees": Decimal("75000"),
        "shares": Decimal("10000"),
    },
    "macro": {
        "gross_mv": Decimal("18000000"),
        "net_mv": Decimal("15000000"),
        "cash": Decimal("3000000"),
        "fees": Decimal("45000"),
        "shares": Decimal("8000"),
    },
    "default": {
        "gross_mv": Decimal("12000000"),
        "net_mv": Decimal("10000000"),
        "cash": Decimal("2000000"),
        "fees": Decimal("30000"),
        "shares": Decimal("5000"),
    },
}


def _nav_profile(portfolio_name: str) -> dict:
    name = portfolio_name.lower()
    if "equity" in name or "l/s" in name:
        return _NAV_PROFILES["equity"]
    if "macro" in name:
        return _NAV_PROFILES["macro"]
    return _NAV_PROFILES["default"]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for EOD runs and NAV snapshots."""
    eod_orchestrator = getattr(app.state, "eod_orchestrator", None)
    if eod_orchestrator is None:
        logger.debug("eod_seed_skipped", reason="orchestrator not available")
        return

    run_repo = eod_orchestrator._run_repo
    nav_repo = getattr(eod_orchestrator, "_nav_calculator", None)
    if nav_repo is not None:
        nav_repo = nav_repo._nav_repo
    else:
        logger.debug("eod_seed_skipped", reason="nav_repo not reachable")
        return

    fund_repo: FundRepository = app.state.fund_repo
    portfolio_repo: PortfolioRepository = app.state.portfolio_repo
    active_funds = await fund_repo.get_all_active()

    runs_seeded = 0
    navs_seeded = 0

    # Seed 5 days of EOD history
    today = date(2026, 4, 11)
    for fund in active_funds:
        for day_offset in range(5, 0, -1):
            biz_date = today - timedelta(days=day_offset)
            # Skip weekends
            if biz_date.weekday() >= 5:
                continue

            # Check if run already exists
            existing = await run_repo.get_latest_run(biz_date, fund.slug)
            if existing is not None:
                continue

            run_id = str(uuid4())
            started = datetime(
                biz_date.year, biz_date.month, biz_date.day, 17, 0, 0, tzinfo=UTC
            )

            await run_repo.create_run(
                run_id=run_id,
                business_date=biz_date,
                fund_slug=fund.slug,
                started_at=started,
            )

            # Save each step as completed
            step_time = started
            for step_name in _STEPS:
                step_duration = timedelta(seconds=15)
                await run_repo.save_step(
                    run_id=run_id,
                    step=step_name,
                    status="completed",
                    started_at=step_time,
                    completed_at=step_time + step_duration,
                    details={"portfolios_processed": 2},
                )
                step_time += step_duration

            # Mark run as completed
            await run_repo.complete_run(
                run_id,
                is_successful=True,
                completed_at=step_time,
            )
            runs_seeded += 1

            # Seed NAV snapshots per portfolio for this date
            portfolios = await portfolio_repo.get_by_fund(fund.id)
            for portfolio in portfolios:
                profile = _nav_profile(portfolio.name)
                nav = profile["net_mv"] + profile["cash"] - profile["fees"]
                nav_per_share = nav / profile["shares"]

                await nav_repo.upsert(
                    portfolio_id=portfolio.id,
                    business_date=biz_date,
                    gross_market_value=profile["gross_mv"],
                    net_market_value=profile["net_mv"],
                    cash_balance=profile["cash"],
                    accrued_fees=profile["fees"],
                    nav=nav,
                    nav_per_share=nav_per_share,
                    shares_outstanding=profile["shares"],
                    currency="USD",
                )
                navs_seeded += 1

    if runs_seeded or navs_seeded:
        logger.info(
            "eod_seed_complete",
            runs=runs_seeded,
            nav_snapshots=navs_seeded,
        )
    else:
        logger.debug("eod_seed_skipped", reason="data already exists")
