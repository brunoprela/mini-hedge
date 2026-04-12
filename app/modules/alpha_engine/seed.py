"""Seed data for alpha engine — what-if scenarios and optimization runs."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.modules.alpha_engine.models.optimization_run import OptimizationRunRecord
from app.modules.alpha_engine.models.optimization_weight import OptimizationWeightRecord
from app.modules.alpha_engine.models.order_intent import OrderIntentRecord
from app.modules.alpha_engine.models.scenario_run import ScenarioRunRecord

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository, PortfolioRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Scenario templates
_SCENARIOS = [
    {
        "name": "Tech Selloff -15%",
        "trades": [
            {"instrument": "AAPL", "side": "sell", "quantity": 500, "reason": "Reduce tech exposure"},
            {"instrument": "MSFT", "side": "sell", "quantity": 300, "reason": "Reduce tech exposure"},
            {"instrument": "JNJ", "side": "buy", "quantity": 400, "reason": "Rotate to defensives"},
        ],
        "result_summary": {
            "portfolio_return": -0.032,
            "benchmark_return": -0.085,
            "active_return": 0.053,
            "var_change_pct": -12.5,
            "tracking_error": 0.045,
        },
    },
    {
        "name": "Rates +100bp Shock",
        "trades": [
            {"instrument": "JPM", "side": "buy", "quantity": 600, "reason": "Banks benefit from higher rates"},
            {"instrument": "AAPL", "side": "sell", "quantity": 200, "reason": "Growth rotation"},
        ],
        "result_summary": {
            "portfolio_return": -0.018,
            "benchmark_return": -0.042,
            "active_return": 0.024,
            "var_change_pct": 5.2,
            "tracking_error": 0.038,
        },
    },
]

# Optimization weights template
_OPT_WEIGHTS = [
    ("AAPL", Decimal("0.12"), Decimal("0.15"), Decimal("0.03"), Decimal("150"), Decimal("37500")),
    ("MSFT", Decimal("0.10"), Decimal("0.12"), Decimal("0.02"), Decimal("120"), Decimal("24000")),
    ("GOOGL", Decimal("0.08"), Decimal("0.09"), Decimal("0.01"), Decimal("30"), Decimal("15000")),
    ("JPM", Decimal("0.06"), Decimal("0.08"), Decimal("0.02"), Decimal("200"), Decimal("20000")),
    ("JNJ", Decimal("0.05"), Decimal("0.07"), Decimal("0.02"), Decimal("250"), Decimal("25000")),
    ("NVDA", Decimal("0.09"), Decimal("0.06"), Decimal("-0.03"), Decimal("-50"), Decimal("-45000")),
]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for alpha engine."""
    alpha_service = getattr(app.state, "alpha_service", None)
    if alpha_service is None:
        logger.debug("alpha_engine_seed_skipped", reason="service not available")
        return

    scenario_repo = alpha_service._scenario_repo
    opt_repo = alpha_service._opt_run_repo
    weight_repo = alpha_service._opt_weight_repo
    intent_repo = alpha_service._intent_repo

    fund_repo: FundRepository = app.state.fund_repo
    portfolio_repo: PortfolioRepository = app.state.portfolio_repo
    active_funds = await fund_repo.get_all_active()

    seeded_scenarios = 0
    seeded_opts = 0
    now = datetime.now(UTC)

    for fund in active_funds:
        portfolios = await portfolio_repo.get_by_fund(fund.id)
        if not portfolios:
            continue

        # Seed only for the first portfolio per fund
        portfolio = portfolios[0]
        pid = portfolio.id

        # Check if already seeded
        existing = await scenario_repo.get_many(
            portfolio_id=pid,
            limit=1,
        )
        if existing:
            continue

        # Seed scenarios
        for scenario in _SCENARIOS:
            record = ScenarioRunRecord(
                id=str(uuid4()),
                portfolio_id=pid,
                scenario_name=scenario["name"],
                trades=scenario["trades"],
                result_summary=scenario["result_summary"],
                status="completed",
                created_at=now,
            )
            await scenario_repo.save(record)
            seeded_scenarios += 1

        # Seed one optimization run with weights and intents
        opt_id = str(uuid4())
        opt_record = OptimizationRunRecord(
            id=opt_id,
            portfolio_id=pid,
            objective="max_sharpe",
            expected_return=Decimal("0.0825"),
            expected_risk=Decimal("0.0412"),
            sharpe_ratio=Decimal("2.003"),
            created_at=now,
        )
        await opt_repo.save(opt_record)

        weights = []
        intents = []
        for ticker, current, target, delta, shares, value in _OPT_WEIGHTS:
            weights.append(
                OptimizationWeightRecord(
                    id=str(uuid4()),
                    optimization_run_id=opt_id,
                    instrument_id=ticker,
                    current_weight=current,
                    target_weight=target,
                    delta_weight=delta,
                    delta_shares=shares,
                    delta_value=value,
                )
            )
            if delta != Decimal(0):
                intents.append(
                    OrderIntentRecord(
                        id=str(uuid4()),
                        optimization_run_id=opt_id,
                        portfolio_id=pid,
                        instrument_id=ticker,
                        side="buy" if delta > 0 else "sell",
                        quantity=abs(int(shares)),
                        estimated_value=abs(value),
                        reason=f"Rebalance {ticker}: {current} → {target}",
                        status="draft",
                        created_at=now,
                    )
                )

        await weight_repo.save_many(weights)
        await intent_repo.save_many(intents)
        seeded_opts += 1

    if seeded_scenarios or seeded_opts:
        logger.info(
            "alpha_engine_seed_complete",
            scenarios=seeded_scenarios,
            optimizations=seeded_opts,
        )
    else:
        logger.debug("alpha_engine_seed_skipped", reason="data already exists")
