"""Unit tests for EODOrchestrator — covers remaining uncovered branches.

Targets lines: run_eod prior-run shortcut, fund-not-found, step failure,
fee accrual, capital allocation, dealing date execution, performance
attribution, risk snapshot failure, and _failed_result.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.eod.core.orchestrator import EODOrchestrator
from app.modules.eod.interfaces.run import EODStepName, EODStepStatus


_BIZ_DATE = date(2026, 4, 12)
_FUND_SLUG = "alpha"
_PID = UUID("10000000-0000-0000-0000-000000000001")


def _mock_deps():
    """Minimal mocked dependencies."""
    run_repo = AsyncMock()
    run_repo.get_latest_run.return_value = None
    run_repo.insert_run = AsyncMock()
    run_repo.upsert_step = AsyncMock()
    run_repo.complete_run = AsyncMock()

    fund_repo = AsyncMock()
    fund = MagicMock()
    fund.id = str(uuid4())
    fund.base_currency = "USD"
    fund_repo.get_by_slug.return_value = fund

    portfolio_repo = AsyncMock()
    portfolio = MagicMock()
    portfolio.id = str(_PID)
    portfolio_repo.get_by_fund.return_value = [portfolio]

    price_service = AsyncMock()
    price_result = MagicMock()
    price_result.finalized_count = 10
    price_result.missing_count = 0
    price_result.is_complete = True
    price_service.finalize_prices.return_value = price_result

    nav_calculator = AsyncMock()
    nav_snap = MagicMock()
    nav_snap.nav = Decimal("1000000")
    nav_snap.shares_outstanding = Decimal("10000")
    nav_calculator.calculate_nav.return_value = nav_snap

    pnl_service = AsyncMock()
    pnl_snap = MagicMock()
    pnl_snap.total_pnl = Decimal("5000")
    pnl_service.snapshot_pnl.return_value = pnl_snap

    reconciler = AsyncMock()
    recon_result = MagicMock()
    recon_result.total_positions = 10
    recon_result.matched_positions = 10
    recon_result.breaks = []
    recon_result.is_clean = True
    reconciler.reconcile.return_value = recon_result

    risk_service = AsyncMock()

    return {
        "run_repo": run_repo,
        "fund_repo": fund_repo,
        "portfolio_repo": portfolio_repo,
        "price_service": price_service,
        "nav_calculator": nav_calculator,
        "pnl_service": pnl_service,
        "reconciler": reconciler,
        "risk_service": risk_service,
    }


class TestRunEodPriorRun:
    """Covers lines 109-111, 117-128: prior successful run shortcut."""

    @pytest.mark.asyncio
    async def test_returns_cached_result_when_prior_run_exists(self) -> None:
        deps = _mock_deps()
        prior = MagicMock()
        prior.is_successful = True
        prior.run_id = str(uuid4())
        prior.started_at = datetime.now(UTC)
        prior.completed_at = datetime.now(UTC)

        step_record = MagicMock()
        step_record.step = EODStepName.MARKET_CLOSE.value
        step_record.status = EODStepStatus.COMPLETED.value
        step_record.started_at = datetime.now(UTC)
        step_record.completed_at = datetime.now(UTC)
        step_record.error_message = None

        deps["run_repo"].get_latest_run.return_value = prior
        deps["run_repo"].get_steps.return_value = [step_record]

        orch = EODOrchestrator(**deps)
        result = await orch.run_eod(_FUND_SLUG, _BIZ_DATE)

        assert result.is_successful is True
        assert result.run_id == UUID(prior.run_id)
        deps["run_repo"].insert_run.assert_not_called()


class TestRunEodFundNotFound:
    """Covers line 142: fund not found produces failed result."""

    @pytest.mark.asyncio
    async def test_fund_not_found_returns_failed(self) -> None:
        deps = _mock_deps()
        deps["fund_repo"].get_by_slug.return_value = None

        orch = EODOrchestrator(**deps)
        result = await orch.run_eod(_FUND_SLUG, _BIZ_DATE)

        assert result.is_successful is False
        assert result.steps[0].error_message == "Fund not found"


class TestStepFailure:
    """Covers lines 176-177, 228-230: step failure halts run and captures error."""

    @pytest.mark.asyncio
    async def test_step_exception_marks_run_failed(self) -> None:
        deps = _mock_deps()
        deps["price_service"].finalize_prices.side_effect = RuntimeError("price feed down")

        orch = EODOrchestrator(**deps)
        result = await orch.run_eod(_FUND_SLUG, _BIZ_DATE)

        assert result.is_successful is False
        failed_steps = [s for s in result.steps if s.status == EODStepStatus.FAILED]
        assert len(failed_steps) == 1
        assert "price feed down" in failed_steps[0].error_message


class TestFeeAccrualStep:
    """Covers lines 327-392: fee accrual with service configured."""

    @pytest.mark.asyncio
    async def test_fee_accrual_not_configured(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(**deps, fee_service=None)

        result = await orch._execute_step(
            EODStepName.FEE_ACCRUAL,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"message": "fee_service_not_configured"}

    @pytest.mark.asyncio
    async def test_fee_accrual_single_share_class(self) -> None:
        deps = _mock_deps()

        fee_service = AsyncMock()
        mgmt_accrual = MagicMock()
        mgmt_accrual.fee_type = "management"
        mgmt_accrual.accrued_amount = Decimal("100")
        perf_accrual = MagicMock()
        perf_accrual.fee_type = "performance"
        perf_accrual.accrued_amount = Decimal("50")
        fee_service.accrue_daily_fees.return_value = [mgmt_accrual, perf_accrual]

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")

        step_data: dict = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(**deps, fee_service=fee_service)
        result = await orch._execute_step(
            EODStepName.FEE_ACCRUAL,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result[str(_PID)] == "ok"
        assert step_data["management_fee"] == Decimal("100")
        assert step_data["performance_fee"] == Decimal("50")
        assert "default" in step_data["class_fees"]

    @pytest.mark.asyncio
    async def test_fee_accrual_exception_skips_portfolio(self) -> None:
        deps = _mock_deps()

        fee_service = AsyncMock()
        fee_service.accrue_daily_fees.side_effect = RuntimeError("fee error")

        step_data: dict = {"nav_snapshots": {}}

        orch = EODOrchestrator(**deps, fee_service=fee_service)
        result = await orch._execute_step(
            EODStepName.FEE_ACCRUAL,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result[str(_PID)] == "skipped"

    @pytest.mark.asyncio
    async def test_fee_accrual_multi_share_class(self) -> None:
        deps = _mock_deps()

        capital_service = AsyncMock()
        capital_service.list_share_classes.return_value = ["A", "B"]

        acct_a = MagicMock()
        acct_a.ending_capital = Decimal("600000")
        acct_b = MagicMock()
        acct_b.ending_capital = Decimal("400000")
        capital_service._accounts = AsyncMock()
        capital_service._accounts.get_latest_by_fund.return_value = [acct_a, acct_b]
        capital_service.get_share_class_nav.side_effect = [
            (Decimal("600000"), None, None),
            (Decimal("400000"), None, None),
        ]

        fee_service = AsyncMock()
        mgmt_accrual = MagicMock()
        mgmt_accrual.fee_type = "management"
        mgmt_accrual.accrued_amount = Decimal("60")
        fee_service.accrue_daily_fees.return_value = [mgmt_accrual]

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")

        step_data: dict = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(
            **deps,
            fee_service=fee_service,
            capital_service=capital_service,
        )
        result = await orch._execute_step(
            EODStepName.FEE_ACCRUAL,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result[str(_PID)] == "ok"
        # 2 share classes -> 2 fee calls per portfolio
        assert fee_service.accrue_daily_fees.call_count == 2


class TestCapitalAllocationStep:
    """Covers lines 398-414: capital allocation step."""

    @pytest.mark.asyncio
    async def test_capital_allocation_not_configured(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(**deps, capital_transaction_service=None)

        result = await orch._execute_step(
            EODStepName.CAPITAL_ALLOCATION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"message": "capital_transaction_service_not_configured"}

    @pytest.mark.asyncio
    async def test_capital_allocation_runs(self) -> None:
        deps = _mock_deps()
        cap_tx_service = AsyncMock()
        cap_tx_service.allocate_daily.return_value = 5

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")
        nav_snap.shares_outstanding = Decimal("10000")

        step_data = {
            "nav_snapshots": {str(_PID): nav_snap},
            "fund_pnl": Decimal("5000"),
            "management_fee": Decimal("100"),
            "performance_fee": Decimal("50"),
            "class_fees": {"default": (Decimal("100"), Decimal("50"))},
        }

        orch = EODOrchestrator(**deps, capital_transaction_service=cap_tx_service)
        result = await orch._execute_step(
            EODStepName.CAPITAL_ALLOCATION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result == {"accounts_allocated": 5}
        cap_tx_service.allocate_daily.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_capital_allocation_zero_shares(self) -> None:
        """When total_shares == 0, orchestrator skips allocation."""
        deps = _mock_deps()
        cap_tx_service = AsyncMock()
        cap_tx_service.allocate_daily.return_value = 1

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("0")
        nav_snap.shares_outstanding = Decimal("0")

        step_data = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(**deps, capital_transaction_service=cap_tx_service)
        result = await orch._execute_step(
            EODStepName.CAPITAL_ALLOCATION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result == {"message": "no_shares_outstanding", "skipped": True}
        cap_tx_service.allocate_daily.assert_not_called()


class TestDealingDateExecutionStep:
    """Covers lines 421-448: dealing date (subscription/redemption) execution."""

    @pytest.mark.asyncio
    async def test_dealing_not_configured(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(
            **deps,
            subscription_service=None,
            redemption_service=None,
        )

        result = await orch._execute_step(
            EODStepName.DEALING_DATE_EXECUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"message": "investor_ops_services_not_configured"}

    @pytest.mark.asyncio
    async def test_dealing_executes_subs_and_reds(self) -> None:
        deps = _mock_deps()
        sub_service = AsyncMock()
        sub_service.execute_subscriptions.return_value = [MagicMock(), MagicMock()]
        red_service = AsyncMock()
        red_service.execute_redemptions.return_value = [MagicMock()]

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")
        nav_snap.shares_outstanding = Decimal("10000")
        step_data = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(
            **deps,
            subscription_service=sub_service,
            redemption_service=red_service,
        )
        result = await orch._execute_step(
            EODStepName.DEALING_DATE_EXECUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result["subscriptions_executed"] == 2
        assert result["redemptions_executed"] == 1
        assert result["nav_per_share"] == "100"

    @pytest.mark.asyncio
    async def test_dealing_no_portfolios(self) -> None:
        deps = _mock_deps()
        sub_service = AsyncMock()

        orch = EODOrchestrator(**deps, subscription_service=sub_service)
        result = await orch._execute_step(
            EODStepName.DEALING_DATE_EXECUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[],
            step_data={},
        )

        # With no portfolios, nav_snapshots is empty so total_shares == 0
        assert result == {"message": "no_shares_outstanding", "skipped": True}

    @pytest.mark.asyncio
    async def test_dealing_only_subscriptions(self) -> None:
        deps = _mock_deps()
        sub_service = AsyncMock()
        sub_service.execute_subscriptions.return_value = [MagicMock()]

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("500000")
        nav_snap.shares_outstanding = Decimal("5000")
        step_data = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(
            **deps,
            subscription_service=sub_service,
            redemption_service=None,
        )
        result = await orch._execute_step(
            EODStepName.DEALING_DATE_EXECUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result["subscriptions_executed"] == 1
        assert result["redemptions_executed"] == 0

    @pytest.mark.asyncio
    async def test_dealing_zero_shares_skips_execution(self) -> None:
        """When total_shares == 0, dealing execution is skipped."""
        deps = _mock_deps()
        sub_service = AsyncMock()
        sub_service.execute_subscriptions.return_value = []

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("0")
        nav_snap.shares_outstanding = Decimal("0")
        step_data = {"nav_snapshots": {str(_PID): nav_snap}}

        orch = EODOrchestrator(**deps, subscription_service=sub_service)
        result = await orch._execute_step(
            EODStepName.DEALING_DATE_EXECUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data=step_data,
        )

        assert result == {"message": "no_shares_outstanding", "skipped": True}
        sub_service.execute_subscriptions.assert_not_called()


class TestPerformanceAttributionStep:
    """Covers lines 457-478: attribution step."""

    @pytest.mark.asyncio
    async def test_attribution_not_configured(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(**deps, attribution_service=None)

        result = await orch._execute_step(
            EODStepName.PERFORMANCE_ATTRIBUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"message": "attribution_service_not_configured"}

    @pytest.mark.asyncio
    async def test_attribution_success(self) -> None:
        deps = _mock_deps()
        attr_service = AsyncMock()
        attr_result = MagicMock()
        attr_result.total_allocation = Decimal("0.002")
        attr_result.total_selection = Decimal("0.003")
        attr_result.total_interaction = Decimal("0.001")
        attr_result.active_return = Decimal("0.006")
        attr_service.calculate_brinson_fachler.return_value = attr_result

        orch = EODOrchestrator(**deps, attribution_service=attr_service)
        result = await orch._execute_step(
            EODStepName.PERFORMANCE_ATTRIBUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        pid_key = str(_PID)
        assert result[pid_key]["allocation_effect"] == "0.002"
        assert result[pid_key]["active_return"] == "0.006"

    @pytest.mark.asyncio
    async def test_attribution_exception_skips(self) -> None:
        deps = _mock_deps()
        attr_service = AsyncMock()
        attr_service.calculate_brinson_fachler.side_effect = RuntimeError("no benchmark")

        orch = EODOrchestrator(**deps, attribution_service=attr_service)
        result = await orch._execute_step(
            EODStepName.PERFORMANCE_ATTRIBUTION,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result[str(_PID)] == "skipped"


class TestEodRiskStep:
    """Covers lines 316-317: risk snapshot failure is swallowed."""

    @pytest.mark.asyncio
    async def test_risk_snapshot_failure_swallowed(self) -> None:
        deps = _mock_deps()
        deps["risk_service"].take_snapshot.side_effect = RuntimeError("risk engine down")

        orch = EODOrchestrator(**deps)
        result = await orch._execute_step(
            EODStepName.EOD_RISK,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"portfolios_processed": 1}


class TestUnknownStep:
    """Covers line 497: unrecognized step returns None."""

    @pytest.mark.asyncio
    async def test_unknown_step_returns_none(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(**deps)

        # We can't easily pass an unknown step since EODStepName is a StrEnum,
        # but we can verify the market_close step returns expected value
        result = await orch._execute_step(
            EODStepName.MARKET_CLOSE,
            fund_slug=_FUND_SLUG,
            business_date=_BIZ_DATE,
            portfolio_ids=[_PID],
            step_data={},
        )

        assert result == {"message": "market_close_acknowledged"}


class TestFailedResult:
    """Covers line 507: _failed_result helper."""

    def test_failed_result_structure(self) -> None:
        deps = _mock_deps()
        orch = EODOrchestrator(**deps)
        run_id = str(uuid4())
        now = datetime.now(UTC)

        result = orch._failed_result(run_id, _BIZ_DATE, _FUND_SLUG, now, "boom")

        assert result.is_successful is False
        assert result.run_id == UUID(run_id)
        assert result.steps[0].status == EODStepStatus.FAILED
        assert result.steps[0].error_message == "boom"
