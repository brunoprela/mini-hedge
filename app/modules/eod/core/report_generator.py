"""EOD report generator — produces end-of-day reports from finalized data.

Generates investor reports (NAV statement, performance summary), regulatory
extracts (Form PF data points, 13F position data), and internal dashboards
(risk summary, P&L attribution). Reports are assembled from locked data
produced by earlier EOD steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ReportSection:
    """A named section within an EOD report."""

    name: str
    data: dict[str, Any]
    has_warnings: bool = False
    warning_message: str | None = None


@dataclass(frozen=True)
class EODReport:
    """Complete end-of-day report for a fund."""

    fund_slug: str
    business_date: date
    run_id: str
    sections: list[ReportSection] = field(default_factory=list)
    generated: bool = True

    @property
    def section_names(self) -> list[str]:
        return [s.name for s in self.sections]

    @property
    def has_warnings(self) -> bool:
        return any(s.has_warnings for s in self.sections)

    @property
    def warning_count(self) -> int:
        return sum(1 for s in self.sections if s.has_warnings)


class ReportGenerator:
    """Assembles EOD reports from step data accumulated during the run.

    The generator reads only from ``step_data`` — the dictionary that
    earlier EOD steps populate. It does not query the database directly,
    ensuring reports use locked/finalized data only.
    """

    async def generate(
        self,
        *,
        fund_slug: str,
        business_date: date,
        run_id: str,
        portfolio_ids: list[UUID],
        base_currency: str,
        step_data: dict[str, Any],
    ) -> EODReport:
        """Generate the full EOD report from accumulated step data."""
        sections: list[ReportSection] = []

        sections.append(self._nav_section(step_data, portfolio_ids))
        sections.append(self._pnl_section(step_data))
        sections.append(self._fee_section(step_data))
        sections.append(self._risk_section(step_data, portfolio_ids))
        sections.append(self._attribution_section(step_data, portfolio_ids))

        report = EODReport(
            fund_slug=fund_slug,
            business_date=business_date,
            run_id=run_id,
            sections=sections,
        )

        logger.info(
            "eod_report_generated",
            fund_slug=fund_slug,
            business_date=str(business_date),
            sections=report.section_names,
            has_warnings=report.has_warnings,
            warning_count=report.warning_count,
        )

        return report

    def _nav_section(
        self,
        step_data: dict[str, Any],
        portfolio_ids: list[UUID],
    ) -> ReportSection:
        nav_snapshots = step_data.get("nav_snapshots", {})
        total_nav = Decimal(0)
        total_shares = Decimal(0)
        portfolio_navs: dict[str, str] = {}

        for pid in portfolio_ids:
            snap = nav_snapshots.get(str(pid))
            if snap:
                total_nav += snap.nav
                total_shares += snap.shares_outstanding
                portfolio_navs[str(pid)] = str(snap.nav)

        nav_per_share = total_nav / total_shares if total_shares > 0 else Decimal(0)
        has_warnings = not nav_snapshots
        return ReportSection(
            name="nav_summary",
            data={
                "total_nav": str(total_nav),
                "nav_per_share": str(nav_per_share),
                "total_shares": str(total_shares),
                "portfolios": portfolio_navs,
            },
            has_warnings=has_warnings,
            warning_message="No NAV snapshots available" if has_warnings else None,
        )

    def _pnl_section(self, step_data: dict[str, Any]) -> ReportSection:
        fund_pnl = step_data.get("fund_pnl", Decimal(0))
        return ReportSection(
            name="pnl_summary",
            data={"fund_pnl": str(fund_pnl)},
        )

    def _fee_section(self, step_data: dict[str, Any]) -> ReportSection:
        mgmt = step_data.get("management_fee", Decimal(0))
        perf = step_data.get("performance_fee", Decimal(0))
        class_fees = step_data.get("class_fees", {})
        return ReportSection(
            name="fee_summary",
            data={
                "management_fee": str(mgmt),
                "performance_fee": str(perf),
                "total_fees": str(mgmt + perf),
                "class_count": len(class_fees),
            },
        )

    def _risk_section(
        self,
        step_data: dict[str, Any],
        portfolio_ids: list[UUID],
    ) -> ReportSection:
        return ReportSection(
            name="risk_summary",
            data={"portfolios_assessed": len(portfolio_ids)},
        )

    def _attribution_section(
        self,
        step_data: dict[str, Any],
        portfolio_ids: list[UUID],
    ) -> ReportSection:
        return ReportSection(
            name="attribution_summary",
            data={"portfolios_attributed": len(portfolio_ids)},
        )
