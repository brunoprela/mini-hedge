"""Regulatory reporting service — generates Form PF, 13F, investor statements."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.modules.regulatory.interfaces import (
    Filing13FEntry,
    Filing13FReport,
    FormPFData,
    FormPFFrequency,
    InvestorStatement,
    MonthlyPerformanceLetter,
)
from app.modules.regulatory.models.investor_statement import InvestorStatementRecord
from app.modules.regulatory.models.performance_letter import PerformanceLetterRecord
from app.modules.regulatory.models.regulatory_filing import RegulatoryFilingRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.services import CapitalAccountService
    from app.modules.exposure.services import ExposureService
    from app.modules.positions.services import PositionService
    from app.modules.regulatory.repositories import (
        InvestorStatementRepository,
        PerformanceLetterRepository,
        RegulatoryFilingRepository,
    )
    from app.modules.risk_engine.services import CounterpartyRiskService
    from app.modules.security_master.services import SecurityMasterService
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)
_2 = Decimal("0.01")
_4 = Decimal("0.0001")
_THOU = Decimal("1000")

_DEFAULT_MINIMUM_INVESTMENT = Decimal("1000000")
_DEFAULT_REDEMPTION_FREQUENCY = "quarterly"
_DEFAULT_PRIMARY_STRATEGY = "Long/Short Equity"
_DEFAULT_STRATEGY_DESCRIPTION = "Fundamental long/short equity with sector rotation"
_13F_SHARE_CLASS = "COM"
_13F_INVESTMENT_DISCRETION = "SOLE"


class RegulatoryService:
    """Generates regulatory filings and investor reports."""

    def __init__(
        self,
        *,
        filing_repo: RegulatoryFilingRepository,
        statement_repo: InvestorStatementRepository,
        letter_repo: PerformanceLetterRepository,
        position_service: PositionService | None = None,
        capital_service: CapitalAccountService | None = None,
        risk_service: CounterpartyRiskService | None = None,
        exposure_service: ExposureService | None = None,
        security_master_service: SecurityMasterService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._filing_repo = filing_repo
        self._statement_repo = statement_repo
        self._letter_repo = letter_repo
        self._positions = position_service
        self._capital = capital_service
        self._risk = risk_service
        self._exposure = exposure_service
        self._sec_master = security_master_service
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # 4A. Form PF
    # ------------------------------------------------------------------

    async def generate_form_pf(
        self,
        fund_slug: str,
        reporting_date: date,
        *,
        fund_name: str = "",
        frequency: FormPFFrequency = FormPFFrequency.QUARTERLY,
        session: AsyncSession | None = None,
    ) -> FormPFData:
        """Aggregate data from positions, risk, exposure, capital into Form PF."""
        now = datetime.now(UTC)

        # Get fund overview from capital accounts
        nav = ZERO
        investor_count = 0
        if self._capital:
            overview = await self._capital.get_fund_overview(session=session)
            nav = overview.total_aum
            investor_count = overview.total_investors

        # Exposure breakdown
        asset_breakdown: list[dict[str, object]] = []
        geo_breakdown: list[dict[str, object]] = []
        gross_notional = ZERO

        # Counterparty data
        cpty_list: list[dict[str, object]] = []
        if self._risk:
            try:
                cptys = await self._risk.list_counterparties(session=session)
                for c in cptys[:5]:
                    cpty_list.append(
                        {
                            "name": c.name,
                            "type": c.counterparty_type,
                            "credit_limit": str(c.credit_limit),
                        }
                    )
            except Exception:
                logger.warning("counterparty_lookup_failed", exc_info=True)

        # Liquidity
        pct_1d = pct_7d = pct_30d = pct_90d = pct_illiq = ZERO
        if self._risk:
            # Placeholder for liquidity calc from risk engine
            pass

        data = FormPFData(
            fund_slug=fund_slug,
            reporting_period_end=reporting_date,
            frequency=frequency,
            fund_name=fund_name or fund_slug,
            gross_asset_value=nav,
            net_asset_value=nav,
            total_investors=investor_count,
            minimum_investment=_DEFAULT_MINIMUM_INVESTMENT,
            gross_notional=gross_notional or nav,
            net_notional=nav,
            leverage_ratio_gross=(
                (gross_notional / nav).quantize(_2)
                if nav > 0 and gross_notional > 0
                else Decimal("1.00")
            ),
            leverage_ratio_net=Decimal("1.00"),
            borrowing_total=ZERO,
            top_counterparties=cpty_list,
            pct_liquidatable_1_day=pct_1d,
            pct_liquidatable_7_days=pct_7d,
            pct_liquidatable_30_days=pct_30d,
            pct_liquidatable_90_days=pct_90d,
            pct_illiquid=pct_illiq,
            investor_liquidity={
                "redemption_frequency": _DEFAULT_REDEMPTION_FREQUENCY,
                "notice_period_days": 45,
                "gate_pct": "0.25",
            },
            asset_class_breakdown=asset_breakdown,
            geographic_breakdown=geo_breakdown,
            primary_strategy=_DEFAULT_PRIMARY_STRATEGY,
            strategy_description=_DEFAULT_STRATEGY_DESCRIPTION,
            generated_at=now,
        )

        # Persist filing record
        record = RegulatoryFilingRecord(
            id=str(uuid4()),
            filing_type="form_pf",
            reporting_period=reporting_date,
            status="draft",
            data=data.model_dump(mode="json"),
            generated_at=now,
        )
        await self._filing_repo.insert(record, session=session)

        logger.info("form_pf_generated", fund_slug=fund_slug, period=str(reporting_date))

        if self._event_bus is not None:
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("regulatory"),
                BaseEvent(
                    event_type=AuditEventType.FORM_PF_GENERATED,
                    data={
                        "filing_id": record.id,
                        "fund_slug": fund_slug,
                        "reporting_period": str(reporting_date),
                        "frequency": frequency.value,
                    },
                    fund_slug=fund_slug,
                    actor_id="regulatory-service",
                ),
            )

        return data

    # ------------------------------------------------------------------
    # 4B. 13F Filing
    # ------------------------------------------------------------------

    async def generate_13f(
        self,
        fund_slug: str,
        reporting_date: date,
        *,
        fund_name: str = "",
        cik: str | None = None,
        portfolio_ids: list[str] | None = None,
        session: AsyncSession | None = None,
    ) -> Filing13FReport:
        """Generate 13F filing data from position snapshots.

        Only includes Section 13(f) securities (US exchange-listed equities).
        """
        now = datetime.now(UTC)
        from uuid import UUID as _UUID

        entries: list[Filing13FEntry] = []
        total_mv = ZERO

        # Aggregate positions across portfolios
        if portfolio_ids and self._positions:
            for pid_str in portfolio_ids:
                pid = _UUID(pid_str)
                positions = await self._positions.get_positions(pid, session=session)
                for pos in positions:
                    mv = (
                        pos.market_value
                        if hasattr(pos, "market_value")
                        else pos.quantity * getattr(pos, "current_price", ZERO)
                    )
                    # Only include equities (13F securities)
                    sec = None
                    if self._sec_master:
                        try:
                            sec = await self._sec_master.get_by_id(
                                _UUID(pos.instrument_id),
                                session=session,
                            )
                        except Exception:
                            logger.warning("security_master_lookup_failed", instrument_id=pos.instrument_id, exc_info=True)
                            sec = None
                    asset_class = getattr(sec, "asset_class", "equity") or "equity"
                    if asset_class != "equity":
                        continue

                    cusip = getattr(sec, "cusip", None) if sec else None
                    name = getattr(sec, "name", pos.instrument_id) if sec else pos.instrument_id
                    mv_thousands = (mv / _THOU).quantize(_2, ROUND_HALF_UP)
                    total_mv += mv_thousands

                    entries.append(
                        Filing13FEntry(
                            issuer_name=name,
                            cusip=cusip,
                            ticker=pos.instrument_id,
                            share_class=_13F_SHARE_CLASS,
                            quantity=pos.quantity,
                            market_value=mv_thousands,
                            investment_discretion=_13F_INVESTMENT_DISCRETION,
                            voting_authority_sole=pos.quantity,
                            voting_authority_shared=ZERO,
                            voting_authority_none=ZERO,
                        )
                    )

        report = Filing13FReport(
            fund_name=fund_name or fund_slug,
            cik=cik,
            reporting_period=reporting_date,
            entries=entries,
            total_market_value=total_mv,
            total_positions=len(entries),
            generated_at=now,
        )

        # Persist
        record = RegulatoryFilingRecord(
            id=str(uuid4()),
            filing_type="13f",
            reporting_period=reporting_date,
            status="draft",
            data=report.model_dump(mode="json"),
            generated_at=now,
        )
        await self._filing_repo.insert(record, session=session)

        logger.info(
            "13f_generated",
            fund_slug=fund_slug,
            period=str(reporting_date),
            positions=len(entries),
        )

        if self._event_bus is not None:
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("regulatory"),
                BaseEvent(
                    event_type=AuditEventType.FILING_13F_GENERATED,
                    data={
                        "filing_id": record.id,
                        "fund_slug": fund_slug,
                        "reporting_period": str(reporting_date),
                        "total_positions": len(entries),
                    },
                    fund_slug=fund_slug,
                    actor_id="regulatory-service",
                ),
            )

        return report

    # ------------------------------------------------------------------
    # 4C. Investor Reporting
    # ------------------------------------------------------------------

    async def generate_investor_statement(
        self,
        investor_id: str,
        period_start: date,
        period_end: date,
        *,
        session: AsyncSession | None = None,
    ) -> InvestorStatement | None:
        """Generate a capital account statement for a single investor."""
        if not self._capital:
            return None

        now = datetime.now(UTC)
        from uuid import UUID as _UUID

        history = await self._capital.get_investor_history(investor_id, session=session)
        if not history:
            return None

        # Find accounts within period
        period_accounts = [a for a in history if period_start <= a.effective_date <= period_end]
        if not period_accounts:
            return None

        latest = period_accounts[0]  # Most recent in period (sorted desc)
        earliest = period_accounts[-1]

        beginning = earliest.beginning_capital
        ending = latest.ending_capital
        contributions = sum((a.contributions for a in period_accounts), ZERO)
        withdrawals = sum((a.withdrawals for a in period_accounts), ZERO)
        mgmt_fees = sum((a.management_fee_allocation for a in period_accounts), ZERO)
        perf_fees = sum((a.performance_fee_allocation for a in period_accounts), ZERO)
        pnl = sum((a.pnl_allocation for a in period_accounts), ZERO)

        gross_ret = pnl
        net_ret = pnl - mgmt_fees - perf_fees
        gross_pct = (gross_ret / beginning).quantize(_4) if beginning > 0 else ZERO
        net_pct = (net_ret / beginning).quantize(_4) if beginning > 0 else ZERO

        # Get nav per share from latest account
        shares = latest.shares_held
        nav_ps = (ending / shares).quantize(_4) if shares > 0 else ZERO

        statement = InvestorStatement(
            investor_id=_UUID(investor_id),
            investor_name=latest.investor_name,
            share_class=latest.share_class,
            period_start=period_start,
            period_end=period_end,
            beginning_capital=beginning,
            contributions=contributions,
            withdrawals=withdrawals,
            gross_return=gross_ret,
            management_fees=mgmt_fees,
            performance_fees=perf_fees,
            net_return=net_ret,
            ending_capital=ending,
            ownership_pct=latest.ownership_pct,
            shares_held=shares,
            nav_per_share=nav_ps,
            gross_return_pct=gross_pct,
            net_return_pct=net_pct,
            ytd_return_pct=net_pct,  # Simplified: same as period
            itd_return_pct=net_pct,
            generated_at=now,
        )

        # Persist
        record = InvestorStatementRecord(
            id=str(uuid4()),
            investor_id=investor_id,
            period_start=period_start,
            period_end=period_end,
            statement_type="quarterly",
            data=statement.model_dump(mode="json"),
            generated_at=now,
        )
        await self._statement_repo.insert(record, session=session)

        if self._event_bus is not None:
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("regulatory"),
                BaseEvent(
                    event_type=AuditEventType.INVESTOR_STATEMENT_GENERATED,
                    data={
                        "statement_id": record.id,
                        "investor_id": investor_id,
                        "period_start": str(period_start),
                        "period_end": str(period_end),
                    },
                    fund_slug=None,
                    actor_id="regulatory-service",
                ),
            )

        return statement

    async def generate_performance_letter(
        self,
        fund_slug: str,
        period_end: date,
        *,
        fund_name: str = "",
        session: AsyncSession | None = None,
    ) -> MonthlyPerformanceLetter:
        """Generate monthly performance letter."""
        now = datetime.now(UTC)

        # Get fund metrics
        nav = ZERO
        investors = 0
        nav_ps = ZERO
        if self._capital:
            overview = await self._capital.get_fund_overview(session=session)
            nav = overview.total_aum
            investors = overview.total_investors
            shares = overview.total_shares_outstanding
            nav_ps = (nav / shares).quantize(_4) if shares > 0 else ZERO

        letter = MonthlyPerformanceLetter(
            fund_name=fund_name or fund_slug,
            fund_slug=fund_slug,
            period=period_end,
            gross_return_pct=ZERO,
            net_return_pct=ZERO,
            benchmark_return_pct=ZERO,
            active_return_pct=ZERO,
            ytd_gross_pct=ZERO,
            ytd_net_pct=ZERO,
            itd_annualized_pct=ZERO,
            total_aum=nav,
            total_investors=investors,
            nav_per_share=nav_ps,
            top_contributors=[],
            top_detractors=[],
            sector_attribution=[],
            risk_metrics={},
            generated_at=now,
        )

        record = PerformanceLetterRecord(
            id=str(uuid4()),
            period=period_end,
            data=letter.model_dump(mode="json"),
            generated_at=now,
        )
        await self._letter_repo.insert(record, session=session)

        logger.info("performance_letter_generated", fund_slug=fund_slug, period=str(period_end))

        if self._event_bus is not None:
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("regulatory"),
                BaseEvent(
                    event_type=AuditEventType.PERFORMANCE_LETTER_GENERATED,
                    data={
                        "letter_id": record.id,
                        "fund_slug": fund_slug,
                        "period": str(period_end),
                    },
                    fund_slug=fund_slug,
                    actor_id="regulatory-service",
                ),
            )

        return letter

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_filings(
        self,
        filing_type: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        records = await self._filing_repo.list_all(filing_type=filing_type, session=session)
        return [
            {
                "id": r.id,
                "filing_type": r.filing_type,
                "reporting_period": str(r.reporting_period),
                "status": r.status,
                "generated_at": str(r.generated_at),
            }
            for r in records
        ]

    async def list_investor_statements(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[InvestorStatement]:
        records = await self._statement_repo.list_all(session=session)
        return [
            InvestorStatement(**r.data)
            for r in records
            if r.data
        ]

    async def list_performance_letters(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[MonthlyPerformanceLetter]:
        records = await self._letter_repo.list_all(session=session)
        return [
            MonthlyPerformanceLetter(**r.data)
            for r in records
            if r.data
        ]
