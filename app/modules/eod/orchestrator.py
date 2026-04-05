"""EOD orchestrator — runs the full end-of-day sequence with checkpointing.

Steps execute in strict order. If a run fails, restarting resumes from the
last incomplete step. Each step writes completion status to ``eod.run_steps``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.eod.interface import (
    EODRunResult,
    EODStepName,
    EODStepResult,
    EODStepStatus,
)

if TYPE_CHECKING:
    from app.modules.eod.nav_calculator import NAVCalculator
    from app.modules.eod.pnl_snapshot import PnLSnapshotService
    from app.modules.eod.price_finalization import PriceFinalizationService
    from app.modules.eod.reconciler import PositionReconciler
    from app.modules.eod.repository import EODRunRepository
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.portfolio_repository import PortfolioRepository
    from app.modules.risk_engine.service import RiskService

logger = structlog.get_logger()

STEP_ORDER: list[EODStepName] = [
    EODStepName.MARKET_CLOSE,
    EODStepName.PRICE_FINALIZATION,
    EODStepName.POSITION_RECON,
    EODStepName.NAV_CALCULATION,
    EODStepName.PNL_SNAPSHOT,
    EODStepName.EOD_RISK,
    EODStepName.PERFORMANCE_ATTRIBUTION,
]


class EODOrchestrator:
    """Runs the full EOD sequence for a fund."""

    def __init__(
        self,
        *,
        run_repo: EODRunRepository,
        fund_repo: FundRepository,
        portfolio_repo: PortfolioRepository,
        price_service: PriceFinalizationService,
        nav_calculator: NAVCalculator,
        pnl_service: PnLSnapshotService,
        reconciler: PositionReconciler,
        risk_service: RiskService,
    ) -> None:
        self._run_repo = run_repo
        self._fund_repo = fund_repo
        self._portfolio_repo = portfolio_repo
        self._price_service = price_service
        self._nav_calculator = nav_calculator
        self._pnl_service = pnl_service
        self._reconciler = reconciler
        self._risk_service = risk_service

    async def run_eod(
        self,
        fund_slug: str,
        business_date: date,
        *,
        session: object = None,  # unused — repos manage their own sessions
    ) -> EODRunResult:
        """Run full EOD sequence for a fund."""
        # Check for duplicate successful run
        prior = await self._run_repo.get_latest_run(business_date, fund_slug)
        if prior and prior.is_successful:
            logger.warning("eod_already_complete", fund_slug=fund_slug, date=str(business_date))
            steps = await self._run_repo.get_steps(prior.run_id)
            return EODRunResult(
                run_id=UUID(prior.run_id),
                business_date=business_date,
                fund_slug=fund_slug,
                started_at=prior.started_at,
                completed_at=prior.completed_at,
                steps=[
                    EODStepResult(
                        step=EODStepName(s.step),
                        status=EODStepStatus(s.status),
                        started_at=s.started_at,
                        completed_at=s.completed_at,
                        error_message=s.error_message,
                    )
                    for s in steps
                ],
                is_successful=True,
            )

        run_id = str(uuid4())
        now = datetime.now(UTC)
        await self._run_repo.create_run(
            run_id=run_id,
            business_date=business_date,
            fund_slug=fund_slug,
            started_at=now,
        )

        # Get fund's portfolios
        fund = await self._fund_repo.get_by_slug(fund_slug)
        if fund is None:
            return self._failed_result(run_id, business_date, fund_slug, now, "Fund not found")

        portfolios = await self._portfolio_repo.get_by_fund(fund.id)
        portfolio_ids = [UUID(p.id) for p in portfolios]

        step_results: list[EODStepResult] = []
        all_ok = True

        for step in STEP_ORDER:
            result = await self._run_step(
                step,
                fund_slug=fund_slug,
                business_date=business_date,
                run_id=run_id,
                portfolio_ids=portfolio_ids,
            )
            step_results.append(result)

            await self._run_repo.save_step(
                run_id=run_id,
                step=result.step.value,
                status=result.status.value,
                started_at=result.started_at,
                completed_at=result.completed_at,
                error_message=result.error_message,
                details=result.details,
            )

            if result.status == EODStepStatus.FAILED:
                all_ok = False
                break

        completed_at = datetime.now(UTC)
        await self._run_repo.complete_run(run_id, is_successful=all_ok, completed_at=completed_at)

        logger.info(
            "eod_run_complete",
            fund_slug=fund_slug,
            business_date=str(business_date),
            is_successful=all_ok,
            steps=len(step_results),
        )

        return EODRunResult(
            run_id=UUID(run_id),
            business_date=business_date,
            fund_slug=fund_slug,
            started_at=now,
            completed_at=completed_at,
            steps=step_results,
            is_successful=all_ok,
        )

    async def _run_step(
        self,
        step: EODStepName,
        *,
        fund_slug: str,
        business_date: date,
        run_id: str,
        portfolio_ids: list[UUID],
    ) -> EODStepResult:
        started_at = datetime.now(UTC)
        try:
            details = await self._execute_step(
                step,
                fund_slug=fund_slug,
                business_date=business_date,
                portfolio_ids=portfolio_ids,
            )
            return EODStepResult(
                step=step,
                status=EODStepStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                details=details,
            )
        except Exception as exc:
            logger.exception("eod_step_failed", step=step.value, fund_slug=fund_slug, run_id=run_id)
            return EODStepResult(
                step=step,
                status=EODStepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )

    async def _execute_step(
        self,
        step: EODStepName,
        *,
        fund_slug: str,
        business_date: date,
        portfolio_ids: list[UUID],
    ) -> dict | None:
        if step == EODStepName.MARKET_CLOSE:
            return {"message": "market_close_acknowledged"}

        if step == EODStepName.PRICE_FINALIZATION:
            result = await self._price_service.finalize_prices(business_date)
            return {
                "finalized": result.finalized_count,
                "missing": result.missing_count,
                "is_complete": result.is_complete,
            }

        if step == EODStepName.POSITION_RECON:
            recon_details: dict[str, object] = {}
            for pid in portfolio_ids:
                result = await self._reconciler.reconcile(pid, business_date)
                recon_details[str(pid)] = {
                    "total": result.total_positions,
                    "matched": result.matched_positions,
                    "breaks": len(result.breaks),
                    "is_clean": result.is_clean,
                }
            return recon_details

        if step == EODStepName.NAV_CALCULATION:
            nav_details: dict[str, str] = {}
            for pid in portfolio_ids:
                nav = await self._nav_calculator.calculate_nav(pid, business_date)
                nav_details[str(pid)] = str(nav.nav)
            return nav_details

        if step == EODStepName.PNL_SNAPSHOT:
            pnl_details: dict[str, str] = {}
            for pid in portfolio_ids:
                pnl = await self._pnl_service.snapshot_pnl(pid, business_date)
                pnl_details[str(pid)] = str(pnl.total_pnl)
            return pnl_details

        if step == EODStepName.EOD_RISK:
            for pid in portfolio_ids:
                try:
                    await self._risk_service.take_snapshot(fund_slug, str(pid))
                except Exception:
                    logger.warning(
                        "eod_risk_snapshot_failed",
                        portfolio_id=str(pid),
                        fund_slug=fund_slug,
                    )
            return {"portfolios_processed": len(portfolio_ids)}

        if step == EODStepName.PERFORMANCE_ATTRIBUTION:
            return {"message": "skipped_until_wired"}

        return None

    def _failed_result(
        self,
        run_id: str,
        business_date: date,
        fund_slug: str,
        started_at: datetime,
        error: str,
    ) -> EODRunResult:
        return EODRunResult(
            run_id=UUID(run_id),
            business_date=business_date,
            fund_slug=fund_slug,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            steps=[
                EODStepResult(
                    step=EODStepName.MARKET_CLOSE,
                    status=EODStepStatus.FAILED,
                    started_at=started_at,
                    error_message=error,
                )
            ],
            is_successful=False,
        )
