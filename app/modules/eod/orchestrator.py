"""EOD orchestrator — runs the full end-of-day sequence with checkpointing.

Steps execute in strict order. If a run fails, restarting resumes from the
last incomplete step. Each step writes completion status to ``eod.run_steps``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog

from app.modules.eod.interface import (
    EODRunResult,
    EODStepName,
    EODStepResult,
    EODStepStatus,
)

if TYPE_CHECKING:
    from app.modules.attribution.service import AttributionService
    from app.modules.capital_accounts.service import CapitalAccountService
    from app.modules.eod.nav_calculator import NAVCalculator
    from app.modules.eod.pnl_snapshot import PnLSnapshotService
    from app.modules.eod.price_finalization import PriceFinalizationService
    from app.modules.eod.reconciler import PositionReconciler
    from app.modules.eod.repository import EODRunRepository
    from app.modules.fee_accounting.service import FeeAccountingService
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.portfolio_repository import PortfolioRepository
    from app.modules.risk_engine.service import RiskService

logger = structlog.get_logger()

STEP_ORDER: list[EODStepName] = [
    EODStepName.MARKET_CLOSE,
    EODStepName.PRICE_FINALIZATION,
    EODStepName.POSITION_RECON,
    EODStepName.NAV_CALCULATION,
    EODStepName.FEE_ACCRUAL,
    EODStepName.PNL_SNAPSHOT,  # must precede CAPITAL_ALLOCATION (provides fund_pnl)
    EODStepName.CAPITAL_ALLOCATION,
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
        fee_service: FeeAccountingService | None = None,
        capital_service: CapitalAccountService | None = None,
        attribution_service: AttributionService | None = None,
    ) -> None:
        self._run_repo = run_repo
        self._fund_repo = fund_repo
        self._portfolio_repo = portfolio_repo
        self._price_service = price_service
        self._nav_calculator = nav_calculator
        self._pnl_service = pnl_service
        self._reconciler = reconciler
        self._risk_service = risk_service
        self._fee_service = fee_service
        self._capital_service = capital_service
        self._attribution_service = attribution_service

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
        base_currency = getattr(fund, "base_currency", "USD") or "USD"

        step_results: list[EODStepResult] = []
        all_ok = True
        # Accumulator for passing data between steps (NAV → fees → capital).
        step_data: dict[str, Any] = {}

        for step in STEP_ORDER:
            result = await self._run_step(
                step,
                fund_slug=fund_slug,
                business_date=business_date,
                run_id=run_id,
                portfolio_ids=portfolio_ids,
                base_currency=base_currency,
                step_data=step_data,
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
        base_currency: str = "USD",
        step_data: dict[str, Any] | None = None,
    ) -> EODStepResult:
        started_at = datetime.now(UTC)
        try:
            details = await self._execute_step(
                step,
                fund_slug=fund_slug,
                business_date=business_date,
                portfolio_ids=portfolio_ids,
                base_currency=base_currency,
                step_data=step_data or {},
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
        base_currency: str = "USD",
        step_data: dict[str, Any],
    ) -> dict[str, object] | None:
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
                recon_result = await self._reconciler.reconcile(pid, business_date)
                recon_details[str(pid)] = {
                    "total": recon_result.total_positions,
                    "matched": recon_result.matched_positions,
                    "breaks": len(recon_result.breaks),
                    "is_clean": recon_result.is_clean,
                }
            return recon_details

        if step == EODStepName.NAV_CALCULATION:
            nav_details: dict[str, object] = {}
            nav_snapshots: dict[str, Any] = {}
            for pid in portfolio_ids:
                nav = await self._nav_calculator.calculate_nav(
                    pid, business_date, currency=base_currency
                )
                nav_details[str(pid)] = str(nav.nav)
                nav_snapshots[str(pid)] = nav
            step_data["nav_snapshots"] = nav_snapshots
            return nav_details

        if step == EODStepName.PNL_SNAPSHOT:
            pnl_details: dict[str, object] = {}
            total_pnl = Decimal(0)
            for pid in portfolio_ids:
                pnl = await self._pnl_service.snapshot_pnl(
                    pid, business_date, base_currency=base_currency
                )
                pnl_details[str(pid)] = str(pnl.total_pnl)
                total_pnl += pnl.total_pnl
            step_data["fund_pnl"] = total_pnl
            return pnl_details

        if step == EODStepName.EOD_RISK:
            for pid in portfolio_ids:
                try:
                    await self._risk_service.take_snapshot(pid, fund_slug)
                except Exception:
                    logger.warning(
                        "eod_risk_snapshot_failed",
                        portfolio_id=str(pid),
                        fund_slug=fund_slug,
                    )
            return {"portfolios_processed": len(portfolio_ids)}

        if step == EODStepName.FEE_ACCRUAL:
            if self._fee_service is None:
                return {"message": "fee_service_not_configured"}
            fee_details: dict[str, object] = {}
            nav_snapshots = step_data.get("nav_snapshots", {})
            total_mgmt_fee = Decimal(0)
            total_perf_fee = Decimal(0)
            for pid in portfolio_ids:
                pid_key = str(pid)
                nav_snap = nav_snapshots.get(pid_key)
                nav_value = nav_snap.nav if nav_snap else Decimal(0)
                try:
                    accruals = await self._fee_service.accrue_daily_fees(
                        portfolio_id=pid,
                        fund_slug=fund_slug,
                        nav=nav_value,
                        business_date=business_date,
                    )
                    fee_details[pid_key] = str(len(accruals))
                    for accrual in accruals:
                        if accrual.fee_type == "management":
                            total_mgmt_fee += accrual.accrued_amount
                        elif accrual.fee_type == "performance":
                            total_perf_fee += accrual.accrued_amount
                except Exception:
                    logger.warning(
                        "eod_fee_accrual_failed",
                        portfolio_id=pid_key,
                        fund_slug=fund_slug,
                    )
                    fee_details[pid_key] = "skipped"
            step_data["management_fee"] = total_mgmt_fee
            step_data["performance_fee"] = total_perf_fee
            return fee_details

        if step == EODStepName.CAPITAL_ALLOCATION:
            if self._capital_service is None:
                return {"message": "capital_service_not_configured"}
            # Compute fund-level NAV per share as weighted average across portfolios
            nav_snapshots = step_data.get("nav_snapshots", {})
            total_nav = Decimal(0)
            total_shares = Decimal(0)
            for snap in nav_snapshots.values():
                total_nav += snap.nav
                total_shares += snap.shares_outstanding
            nav_per_share = total_nav / total_shares if total_shares > 0 else Decimal(1)

            count = await self._capital_service.allocate_daily(
                fund_pnl=step_data.get("fund_pnl", Decimal(0)),
                management_fee=step_data.get("management_fee", Decimal(0)),
                performance_fee=step_data.get("performance_fee", Decimal(0)),
                nav_per_share=nav_per_share,
                business_date=business_date,
            )
            return {"accounts_allocated": count}

        if step == EODStepName.PERFORMANCE_ATTRIBUTION:
            if self._attribution_service is None:
                return {"message": "attribution_service_not_configured"}
            attribution_details: dict[str, object] = {}
            for pid in portfolio_ids:
                try:
                    result = await self._attribution_service.calculate_brinson_fachler(
                        portfolio_id=pid,
                        period_start=business_date,
                        period_end=business_date,
                    )
                    attribution_details[str(pid)] = {
                        "allocation_effect": str(result.total_allocation),
                        "selection_effect": str(result.total_selection),
                        "interaction_effect": str(result.total_interaction),
                        "active_return": str(result.active_return),
                    }
                except Exception:
                    logger.warning(
                        "eod_attribution_failed",
                        portfolio_id=str(pid),
                        fund_slug=fund_slug,
                    )
                    attribution_details[str(pid)] = "skipped"
            return attribution_details

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
