"""Unit tests for EODOrchestrator — corporate action step + step ordering."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.eod.core.orchestrator import EODOrchestrator, STEP_ORDER
from app.modules.eod.interfaces.run import EODStepName, EODStepStatus


def _mock_repos_and_services():
    """Create minimal mocked dependencies for the orchestrator."""
    run_repo = AsyncMock()
    run_repo.get_latest_run.return_value = None
    run_repo.create_run = AsyncMock()
    run_repo.save_step = AsyncMock()
    run_repo.complete_run = AsyncMock()

    fund_repo = AsyncMock()
    fund = MagicMock()
    fund.id = str(uuid4())
    fund.base_currency = "USD"
    fund_repo.get_by_slug.return_value = fund

    portfolio_repo = AsyncMock()
    portfolio = MagicMock()
    portfolio.id = str(uuid4())
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


class TestStepOrder:
    def test_corporate_action_step_exists_in_enum(self) -> None:
        assert hasattr(EODStepName, "CORPORATE_ACTION_PROCESSING")
        assert EODStepName.CORPORATE_ACTION_PROCESSING == "corporate_action_processing"

    def test_corporate_action_after_price_finalization(self) -> None:
        price_idx = STEP_ORDER.index(EODStepName.PRICE_FINALIZATION)
        ca_idx = STEP_ORDER.index(EODStepName.CORPORATE_ACTION_PROCESSING)
        recon_idx = STEP_ORDER.index(EODStepName.POSITION_RECON)
        assert ca_idx == price_idx + 1
        assert ca_idx < recon_idx

    def test_step_order_has_12_steps(self) -> None:
        assert len(STEP_ORDER) == 12


class TestCorporateActionStep:
    @pytest.mark.asyncio
    async def test_corporate_action_step_calls_service(self) -> None:
        deps = _mock_repos_and_services()
        ca_service = AsyncMock()
        action = MagicMock()
        action.action_type = "stock_split"
        ca_service.fetch_and_process.return_value = [action]

        orch = EODOrchestrator(
            **deps,
            corporate_actions_service=ca_service,
        )

        result = await orch._execute_step(
            EODStepName.CORPORATE_ACTION_PROCESSING,
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            portfolio_ids=[UUID("10000000-0000-0000-0000-000000000001")],
            step_data={},
        )

        ca_service.fetch_and_process.assert_awaited_once()
        call_kwargs = ca_service.fetch_and_process.call_args
        assert call_kwargs.kwargs["fund_slug"] == "alpha"
        assert result is not None
        pid_key = "10000000-0000-0000-0000-000000000001"
        assert result[pid_key]["processed"] == 1
        assert "stock_split" in result[pid_key]["types"]

    @pytest.mark.asyncio
    async def test_corporate_action_step_without_service(self) -> None:
        deps = _mock_repos_and_services()
        orch = EODOrchestrator(**deps, corporate_actions_service=None)

        result = await orch._execute_step(
            EODStepName.CORPORATE_ACTION_PROCESSING,
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            portfolio_ids=[UUID("10000000-0000-0000-0000-000000000001")],
            step_data={},
        )

        assert result == {"message": "corporate_actions_service_not_configured"}

    @pytest.mark.asyncio
    async def test_corporate_action_step_no_actions(self) -> None:
        deps = _mock_repos_and_services()
        ca_service = AsyncMock()
        ca_service.fetch_and_process.return_value = []

        orch = EODOrchestrator(**deps, corporate_actions_service=ca_service)

        result = await orch._execute_step(
            EODStepName.CORPORATE_ACTION_PROCESSING,
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            portfolio_ids=[UUID("10000000-0000-0000-0000-000000000001")],
            step_data={},
        )

        pid_key = "10000000-0000-0000-0000-000000000001"
        assert result[pid_key]["processed"] == 0
        assert result[pid_key]["types"] == []

    @pytest.mark.asyncio
    async def test_full_eod_run_includes_corporate_actions(self) -> None:
        deps = _mock_repos_and_services()
        ca_service = AsyncMock()
        ca_service.fetch_and_process.return_value = []

        orch = EODOrchestrator(**deps, corporate_actions_service=ca_service)

        result = await orch.run_eod("alpha", date(2026, 4, 12))

        assert result.is_successful
        step_names = [s.step for s in result.steps]
        assert EODStepName.CORPORATE_ACTION_PROCESSING in step_names
        # Verify it ran before position recon
        ca_idx = step_names.index(EODStepName.CORPORATE_ACTION_PROCESSING)
        recon_idx = step_names.index(EODStepName.POSITION_RECON)
        assert ca_idx < recon_idx
