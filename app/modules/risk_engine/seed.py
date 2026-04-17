"""Seed data for risk engine — counterparties, risk snapshots, stress tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.risk_engine.models.counterparty import CounterpartyRecord
from app.modules.risk_engine.models.risk_snapshot import RiskSnapshotRecord

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository, PortfolioRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Fixed counterparty UUIDs for deterministic seeding
_CPTY_GS_ID = "80000000-0000-0000-0000-000000000001"
_CPTY_JPM_ID = "80000000-0000-0000-0000-000000000002"
_CPTY_MS_ID = "80000000-0000-0000-0000-000000000003"
_CPTY_BNYM_ID = "80000000-0000-0000-0000-000000000004"

_COUNTERPARTIES = [
    CounterpartyRecord(
        id=_CPTY_GS_ID,
        name="Goldman Sachs",
        counterparty_type="prime_broker",
        credit_rating="A+",
        credit_limit=Decimal("50000000"),
        netting_eligible=True,
        is_active=True,
    ),
    CounterpartyRecord(
        id=_CPTY_JPM_ID,
        name="JP Morgan",
        counterparty_type="broker",
        credit_rating="AA-",
        credit_limit=Decimal("75000000"),
        netting_eligible=True,
        is_active=True,
    ),
    CounterpartyRecord(
        id=_CPTY_MS_ID,
        name="Morgan Stanley",
        counterparty_type="broker",
        credit_rating="A",
        credit_limit=Decimal("30000000"),
        netting_eligible=True,
        is_active=True,
    ),
    CounterpartyRecord(
        id=_CPTY_BNYM_ID,
        name="BNY Mellon",
        counterparty_type="custodian",
        credit_rating="AA",
        credit_limit=Decimal("100000000"),
        netting_eligible=False,
        is_active=True,
    ),
]

# Realistic risk snapshot profiles per portfolio strategy
_RISK_PROFILES: dict[str, dict] = {
    # Equity L/S: moderate VaR, decent Sharpe
    "Equity L/S": {
        "nav": Decimal("25000000"),
        "var_95_1d": Decimal("312500"),
        "var_99_1d": Decimal("500000"),
        "expected_shortfall_95": Decimal("437500"),
        "max_drawdown": Decimal("0.082"),
        "sharpe_ratio": Decimal("1.45"),
    },
    # Global Macro: higher VaR, lower Sharpe
    "Global Macro": {
        "nav": Decimal("15000000"),
        "var_95_1d": Decimal("225000"),
        "var_99_1d": Decimal("375000"),
        "expected_shortfall_95": Decimal("315000"),
        "max_drawdown": Decimal("0.105"),
        "sharpe_ratio": Decimal("0.92"),
    },
    # Stat Arb: low VaR, high Sharpe
    "Stat Arb": {
        "nav": Decimal("20000000"),
        "var_95_1d": Decimal("140000"),
        "var_99_1d": Decimal("220000"),
        "expected_shortfall_95": Decimal("196000"),
        "max_drawdown": Decimal("0.035"),
        "sharpe_ratio": Decimal("2.10"),
    },
    # Default for any strategy
    "default": {
        "nav": Decimal("10000000"),
        "var_95_1d": Decimal("150000"),
        "var_99_1d": Decimal("250000"),
        "expected_shortfall_95": Decimal("210000"),
        "max_drawdown": Decimal("0.065"),
        "sharpe_ratio": Decimal("1.15"),
    },
}


def _profile_for(portfolio_name: str) -> dict:
    """Match portfolio name to a risk profile."""
    name = portfolio_name.lower()
    if "equity" in name or "l/s" in name or "long" in name:
        return _RISK_PROFILES["Equity L/S"]
    if "macro" in name:
        return _RISK_PROFILES["Global Macro"]
    if "stat" in name or "arb" in name or "neutral" in name:
        return _RISK_PROFILES["Stat Arb"]
    return _RISK_PROFILES["default"]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for risk engine."""
    counterparty_service = getattr(app.state, "counterparty_risk_service", None)
    risk_service = getattr(app.state, "risk_snapshot_service", None)
    if counterparty_service is None or risk_service is None:
        logger.debug("risk_engine_seed_skipped", reason="services not available")
        return

    cpty_repo = counterparty_service._counterparty_repo
    snapshot_repo = risk_service._snapshot_repo

    fund_repo: FundRepository = app.state.fund_repo
    portfolio_repo: PortfolioRepository = app.state.portfolio_repo
    active_funds = await fund_repo.list_active()

    cpty_seeded = 0
    snap_seeded = 0
    now = datetime.now(UTC)

    for fund in active_funds:
        async with sf.fund_scope(fund.slug):
            # Seed counterparties (per-fund schema)
            existing = await cpty_repo.list_counterparties()
            existing_ids = {r.id for r in existing}
            for cpty in _COUNTERPARTIES:
                if cpty.id in existing_ids:
                    continue
                await cpty_repo.insert_counterparty(cpty)
                cpty_seeded += 1

            # Seed risk snapshots (one per portfolio, 5 days of history)
            portfolios = await portfolio_repo.get_by_fund(fund.id)
            for portfolio in portfolios:
                existing_snap = await snapshot_repo.get_latest_snapshot(
                    UUID(portfolio.id),
                )
                if existing_snap is not None:
                    continue

                profile = _profile_for(portfolio.name)
                # Create 5 days of history
                for day_offset in range(5, 0, -1):
                    snap_time = now - timedelta(days=day_offset)
                    # Add small daily variation (±2%)
                    factor = Decimal("1") + Decimal(str((day_offset % 3 - 1) * 0.01))
                    record = RiskSnapshotRecord(
                        id=str(uuid4()),
                        portfolio_id=portfolio.id,
                        nav=profile["nav"] * factor,
                        var_95_1d=profile["var_95_1d"] * factor,
                        var_99_1d=profile["var_99_1d"] * factor,
                        expected_shortfall_95=profile["expected_shortfall_95"] * factor,
                        max_drawdown=profile["max_drawdown"],
                        sharpe_ratio=profile["sharpe_ratio"],
                        snapshot_at=snap_time,
                    )
                    await snapshot_repo.insert_snapshot(record)
                    snap_seeded += 1

    if cpty_seeded or snap_seeded:
        logger.info(
            "risk_engine_seed_complete",
            counterparties=cpty_seeded,
            snapshots=snap_seeded,
        )
    else:
        logger.debug("risk_engine_seed_skipped", reason="data already exists")
