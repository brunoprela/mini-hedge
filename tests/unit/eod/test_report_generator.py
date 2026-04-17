"""Unit tests for EOD ReportGenerator and REPORT_GENERATION step."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.eod.core.orchestrator import EODOrchestrator, STEP_ORDER
from app.modules.eod.core.report_generator import EODReport, ReportGenerator, ReportSection
from app.modules.eod.interfaces.run import EODStepName, EODStepStatus


class TestReportSection:
    def test_create_section(self) -> None:
        section = ReportSection(name="nav_summary", data={"total_nav": "1000000"})
        assert section.name == "nav_summary"
        assert not section.has_warnings

    def test_section_with_warnings(self) -> None:
        section = ReportSection(
            name="nav_summary",
            data={},
            has_warnings=True,
            warning_message="No NAV snapshots available",
        )
        assert section.has_warnings
        assert section.warning_message == "No NAV snapshots available"


class TestEODReport:
    def test_section_names(self) -> None:
        report = EODReport(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            sections=[
                ReportSection(name="nav_summary", data={}),
                ReportSection(name="pnl_summary", data={}),
            ],
        )
        assert report.section_names == ["nav_summary", "pnl_summary"]

    def test_has_warnings(self) -> None:
        report = EODReport(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            sections=[
                ReportSection(name="nav", data={}, has_warnings=True),
                ReportSection(name="pnl", data={}),
            ],
        )
        assert report.has_warnings
        assert report.warning_count == 1

    def test_no_warnings(self) -> None:
        report = EODReport(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            sections=[ReportSection(name="pnl", data={})],
        )
        assert not report.has_warnings
        assert report.warning_count == 0


class TestReportGenerator:
    @pytest.mark.asyncio
    async def test_generate_full_report(self) -> None:
        gen = ReportGenerator()
        pid = uuid4()

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")
        nav_snap.shares_outstanding = Decimal("10000")

        step_data = {
            "nav_snapshots": {str(pid): nav_snap},
            "fund_pnl": Decimal("5000"),
            "management_fee": Decimal("100"),
            "performance_fee": Decimal("50"),
            "class_fees": {"default": (Decimal("100"), Decimal("50"))},
        }

        report = await gen.generate(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            portfolio_ids=[pid],
            base_currency="USD",
            step_data=step_data,
        )

        assert report.generated
        assert report.fund_slug == "alpha"
        assert len(report.sections) == 5
        assert "nav_summary" in report.section_names
        assert "pnl_summary" in report.section_names
        assert "fee_summary" in report.section_names
        assert "risk_summary" in report.section_names
        assert "attribution_summary" in report.section_names

    @pytest.mark.asyncio
    async def test_generate_with_no_nav_warns(self) -> None:
        gen = ReportGenerator()
        report = await gen.generate(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            portfolio_ids=[uuid4()],
            base_currency="USD",
            step_data={},
        )
        # NAV section should warn about missing data
        nav_section = next(s for s in report.sections if s.name == "nav_summary")
        assert nav_section.has_warnings

    @pytest.mark.asyncio
    async def test_nav_section_calculates_per_share(self) -> None:
        gen = ReportGenerator()
        pid = uuid4()
        nav_snap = MagicMock()
        nav_snap.nav = Decimal("2000000")
        nav_snap.shares_outstanding = Decimal("20000")

        step_data = {"nav_snapshots": {str(pid): nav_snap}}

        report = await gen.generate(
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            run_id="run-1",
            portfolio_ids=[pid],
            base_currency="USD",
            step_data=step_data,
        )
        nav_section = next(s for s in report.sections if s.name == "nav_summary")
        assert nav_section.data["nav_per_share"] == "100"
        assert nav_section.data["total_nav"] == "2000000"


class TestReportGenerationStep:
    def test_report_generation_in_enum(self) -> None:
        assert hasattr(EODStepName, "REPORT_GENERATION")
        assert EODStepName.REPORT_GENERATION == "report_generation"

    def test_report_generation_is_last_step(self) -> None:
        assert STEP_ORDER[-1] == EODStepName.REPORT_GENERATION

    def test_step_order_has_12_steps(self) -> None:
        assert len(STEP_ORDER) == 12

    @pytest.mark.asyncio
    async def test_report_step_without_generator(self) -> None:
        deps = _mock_repos_and_services()
        orch = EODOrchestrator(**deps, report_generator=None)

        result = await orch._execute_step(
            EODStepName.REPORT_GENERATION,
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            portfolio_ids=[UUID("10000000-0000-0000-0000-000000000001")],
            step_data={},
        )
        assert result == {"message": "report_generator_not_configured"}

    @pytest.mark.asyncio
    async def test_report_step_with_generator(self) -> None:
        deps = _mock_repos_and_services()
        gen = ReportGenerator()
        orch = EODOrchestrator(**deps, report_generator=gen)

        nav_snap = MagicMock()
        nav_snap.nav = Decimal("1000000")
        nav_snap.shares_outstanding = Decimal("10000")
        pid = UUID("10000000-0000-0000-0000-000000000001")

        step_data = {
            "nav_snapshots": {str(pid): nav_snap},
            "fund_pnl": Decimal("5000"),
        }

        result = await orch._execute_step(
            EODStepName.REPORT_GENERATION,
            fund_slug="alpha",
            business_date=date(2026, 4, 12),
            portfolio_ids=[pid],
            step_data=step_data,
        )
        assert "sections" in result
        assert "nav_summary" in result["sections"]
        assert isinstance(result["has_warnings"], bool)


def _mock_repos_and_services():
    """Create minimal mocked dependencies for the orchestrator."""
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
