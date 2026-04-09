"""Risk engine service — calculates and persists risk metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import numpy as np
import structlog

from app.modules.risk_engine.calculator import (
    calculate_factor_decomposition,
    calculate_historical_var,
    calculate_liquidity_profile,
    calculate_margin_requirements,
    calculate_parametric_var,
    run_stress_test,
)
from app.modules.risk_engine.interface import (
    CounterpartyExposure,
    CounterpartyInfo,
    CounterpartyType,
    FactorDecomposition,
    LiquidityProfile,
    MarginSummary,
    RiskSnapshot,
    StressScenario,
    StressTestResult,
    VaRMethod,
    VaRResult,
)
from app.modules.risk_engine.models import (
    CounterpartyExposureRecord,
    LiquidityProfileRecord,
    MarginRequirementRecord,
    RiskSnapshotRecord,
    StressPositionImpactRecord,
    StressTestResultRecord,
    VaRContributionRecord,
    VaRResultRecord,
)
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.market_data.fx import FXConverter
    from app.modules.market_data.service import MarketDataService
    from app.modules.positions.service import PositionService
    from app.modules.risk_engine.repository import RiskRepository
    from app.modules.security_master.service import SecurityMasterService
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)
# Minimum number of price history days needed for VaR
MIN_HISTORY_DAYS = 30
# Default lookback window for historical VaR
DEFAULT_LOOKBACK = 252


class RiskService:
    """Calculates portfolio risk metrics."""

    def __init__(
        self,
        *,
        risk_repo: RiskRepository,
        position_service: PositionService,
        market_data_service: MarketDataService,
        security_master_service: SecurityMasterService,
        event_bus: EventBus | None = None,
        fx_converter: FXConverter | None = None,
        base_currency: str = "USD",
    ) -> None:
        self._risk_repo = risk_repo
        self._position_service = position_service
        self._market_data_service = market_data_service
        self._security_master_service = security_master_service
        self._event_bus = event_bus
        self._fx = fx_converter
        self._base_currency = base_currency

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_latest_snapshot(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> RiskSnapshot | None:
        record = await self._risk_repo.get_latest_snapshot(portfolio_id, session=session)
        if record is None:
            return None
        return RiskSnapshot(
            id=UUID(str(record.id)),
            portfolio_id=UUID(str(record.portfolio_id)),
            nav=record.nav,
            var_95_1d=record.var_95_1d,
            var_99_1d=record.var_99_1d,
            expected_shortfall_95=record.expected_shortfall_95,
            max_drawdown=record.max_drawdown,
            sharpe_ratio=record.sharpe_ratio,
            snapshot_at=record.snapshot_at,
        )

    async def get_snapshot_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[RiskSnapshot]:
        records = await self._risk_repo.get_snapshot_history(
            portfolio_id, start, end, session=session
        )
        return [
            RiskSnapshot(
                id=UUID(r.id),
                portfolio_id=UUID(r.portfolio_id),
                nav=r.nav,
                var_95_1d=r.var_95_1d,
                var_99_1d=r.var_99_1d,
                expected_shortfall_95=r.expected_shortfall_95,
                max_drawdown=r.max_drawdown,
                sharpe_ratio=r.sharpe_ratio,
                snapshot_at=r.snapshot_at,
            )
            for r in records
        ]

    async def calculate_var(
        self,
        portfolio_id: UUID,
        method: VaRMethod = VaRMethod.HISTORICAL,
        confidence: float = 0.95,
        horizon_days: int = 1,
        *,
        session: AsyncSession | None = None,
    ) -> VaRResult:
        """Calculate VaR for a portfolio."""
        weights, returns_matrix, instrument_ids, nav = await self._build_risk_inputs(
            portfolio_id, session=session
        )

        if returns_matrix.size == 0:
            return VaRResult(
                portfolio_id=portfolio_id,
                method=method,
                confidence_level=confidence,
                horizon_days=horizon_days,
                var_amount=ZERO,
                var_pct=ZERO,
                expected_shortfall=ZERO,
                contributions=[],
                calculated_at=datetime.now(UTC),
            )

        if method == VaRMethod.HISTORICAL:
            result = calculate_historical_var(
                portfolio_id,
                weights,
                returns_matrix,
                instrument_ids,
                confidence,
                horizon_days,
                nav,
            )
        else:
            result = calculate_parametric_var(
                portfolio_id,
                weights,
                returns_matrix,
                instrument_ids,
                confidence,
                horizon_days,
                nav,
            )

        # Persist
        await self._persist_var_result(result, session=session)

        logger.info(
            "var_calculated",
            portfolio_id=str(portfolio_id),
            method=method,
            var_amount=str(result.var_amount),
        )
        return result

    async def run_stress_test(
        self,
        portfolio_id: UUID,
        scenario: StressScenario,
        *,
        session: AsyncSession | None = None,
    ) -> StressTestResult:
        """Run a stress test scenario on a portfolio."""
        positions_data, nav = await self._build_stress_inputs(portfolio_id, session=session)

        result = run_stress_test(portfolio_id, scenario, positions_data, nav)

        # Persist
        await self._persist_stress_result(result, scenario, session=session)

        logger.info(
            "stress_test_run",
            portfolio_id=str(portfolio_id),
            scenario=scenario.name,
            impact=str(result.total_pnl_impact),
        )
        return result

    async def calculate_factor_model(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> FactorDecomposition:
        """Calculate factor decomposition for a portfolio."""
        weights, returns_matrix, instrument_ids, nav = await self._build_risk_inputs(
            portfolio_id, session=session
        )

        instruments = await self._security_master_service.get_all_active(session=session)
        sector_lookup = {i.ticker: i.sector or "Unknown" for i in instruments}
        sector_map = {iid: sector_lookup.get(iid, "Unknown") for iid in instrument_ids}

        # Build currency map from positions
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        currency_map = {p.instrument_id: p.currency for p in positions}

        result = calculate_factor_decomposition(
            portfolio_id,
            weights,
            returns_matrix,
            instrument_ids,
            sector_map,
            nav,
            currency_map=currency_map,
            base_currency=self._base_currency,
        )

        logger.info(
            "factor_decomposition_calculated",
            portfolio_id=str(portfolio_id),
            systematic_pct=str(result.systematic_pct),
        )
        return result

    async def take_snapshot(
        self,
        portfolio_id: UUID,
        fund_slug: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> RiskSnapshot:
        """Calculate and persist a complete risk snapshot."""
        var_95 = await self.calculate_var(
            portfolio_id,
            VaRMethod.HISTORICAL,
            0.95,
            1,
            session=session,
        )
        var_99 = await self.calculate_var(
            portfolio_id,
            VaRMethod.HISTORICAL,
            0.99,
            1,
            session=session,
        )
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        nav = sum(
            (p.market_value for p in positions if p.market_value),
            ZERO,
        )

        record = RiskSnapshotRecord(
            portfolio_id=str(portfolio_id),
            nav=nav,
            var_95_1d=var_95.var_amount,
            var_99_1d=var_99.var_amount,
            expected_shortfall_95=var_95.expected_shortfall,
            max_drawdown=ZERO,  # would need historical NAV series
            snapshot_at=datetime.now(UTC),
        )
        await self._risk_repo.save_snapshot(record, session=session)
        await self._publish_risk_event(record, fund_slug)

        return RiskSnapshot(
            id=UUID(str(record.id)),
            portfolio_id=UUID(str(record.portfolio_id)),
            nav=record.nav,
            var_95_1d=record.var_95_1d,
            var_99_1d=record.var_99_1d,
            expected_shortfall_95=record.expected_shortfall_95,
            max_drawdown=record.max_drawdown,
            sharpe_ratio=record.sharpe_ratio,
            snapshot_at=record.snapshot_at,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _build_risk_inputs(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[dict[str, float], np.ndarray, list[str], float]:
        """Build weights, returns matrix, instrument list, and NAV.

        Market values are converted to base currency via FXConverter when
        available, ensuring weights and NAV reflect a single currency.
        """
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        positions = [p for p in positions if p.quantity != ZERO]

        if not positions:
            return {}, np.empty((0, 0)), [], 0.0

        # Convert market values to base currency
        base_values: dict[str, float] = {}
        for p in positions:
            mv = p.market_value or ZERO
            if self._fx is not None and p.currency != self._base_currency:
                converted = self._fx.convert(mv, p.currency, self._base_currency)
                if converted is not None:
                    mv = converted
            base_values[p.instrument_id] = float(mv)

        nav = sum(base_values.values())
        if nav == 0:
            return {}, np.empty((0, 0)), [], 0.0

        instrument_ids = [p.instrument_id for p in positions]
        weights = {iid: base_values[iid] / nav for iid in instrument_ids}

        # Build returns matrix — FX-adjusted when converter is available
        currency_map = {p.instrument_id: p.currency for p in positions}
        returns_matrix = await self._build_returns_matrix(
            instrument_ids, currency_map=currency_map, session=session
        )

        return weights, returns_matrix, instrument_ids, nav

    async def _build_returns_matrix(
        self,
        instrument_ids: list[str],
        *,
        currency_map: dict[str, str] | None = None,
        session: AsyncSession | None = None,
    ) -> np.ndarray:
        """Build a (n_days, n_instruments) returns matrix.

        Uses synthetic returns based on instrument reference data (annual_drift,
        annual_volatility) until real price history is available.

        When *currency_map* and *fx_converter* are available, local-currency
        returns are adjusted to base-currency returns:
          base_return = (1 + local_return) * (1 + fx_return) - 1
        """
        n = len(instrument_ids)
        if n == 0:
            return np.empty((0, 0))

        # Look up drift/volatility from instrument reference data
        instruments = await self._security_master_service.get_all_active(session=session)
        vol_map = {
            i.ticker: i.annual_volatility for i in instruments if i.annual_volatility is not None
        }
        drift_map = {i.ticker: i.annual_drift for i in instruments if i.annual_drift is not None}

        n_days = DEFAULT_LOOKBACK
        daily_returns = np.zeros((n_days, n))

        for i, iid in enumerate(instrument_ids):
            annual_vol = vol_map.get(iid, 0.25)
            annual_drift = drift_map.get(iid, 0.08)
            daily_vol = annual_vol / np.sqrt(252)
            daily_drift = annual_drift / 252
            local_returns = np.random.normal(daily_drift, daily_vol, n_days)

            # Apply FX adjustment for non-base-currency positions
            ccy = currency_map.get(iid) if currency_map else None
            if ccy and ccy != self._base_currency and self._fx is not None:
                # Simulate FX return series (zero drift, ~8% annual vol)
                fx_daily_vol = 0.08 / np.sqrt(252)
                fx_returns = np.random.normal(0.0, fx_daily_vol, n_days)
                daily_returns[:, i] = (1 + local_returns) * (1 + fx_returns) - 1
            else:
                daily_returns[:, i] = local_returns

        return daily_returns

    async def _build_stress_inputs(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[dict[str, tuple[Decimal, str | None]], float]:
        """Build position data for stress testing."""
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        positions = [p for p in positions if p.quantity != ZERO]

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))

        # Batch-fetch instruments instead of N+1
        instruments = await self._security_master_service.get_all_active(session=session)
        sector_map = {i.ticker: getattr(i, "sector", None) for i in instruments}

        positions_data: dict[str, tuple[Decimal, str | None]] = {}
        for p in positions:
            positions_data[p.instrument_id] = (
                p.market_value or ZERO,
                sector_map.get(p.instrument_id),
            )

        return positions_data, nav

    async def _publish_risk_event(
        self,
        record: RiskSnapshotRecord,
        fund_slug: str | None,
    ) -> None:
        """Publish a risk.updated event to Kafka."""
        if self._event_bus is None or not fund_slug:
            return

        event = BaseEvent(
            event_type=AuditEventType.RISK_UPDATED,
            data={
                "portfolio_id": record.portfolio_id,
                "nav": str(record.nav),
                "var_95_1d": str(record.var_95_1d),
                "var_99_1d": str(record.var_99_1d),
                "expected_shortfall_95": str(record.expected_shortfall_95),
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "risk.updated"),
            event,
        )

    async def _persist_var_result(
        self, result: VaRResult, *, session: AsyncSession | None = None
    ) -> None:
        """Persist VaR result and contributions."""
        result_record = VaRResultRecord(
            portfolio_id=str(result.portfolio_id),
            method=result.method,
            confidence_level=result.confidence_level,
            horizon_days=result.horizon_days,
            var_amount=result.var_amount,
            var_pct=result.var_pct,
            expected_shortfall=result.expected_shortfall,
            calculated_at=result.calculated_at,
        )

        contributions = [
            VaRContributionRecord(
                var_result_id=result_record.id,
                instrument_id=c.instrument_id,
                weight=c.weight,
                marginal_var=c.marginal_var,
                component_var=c.component_var,
                pct_contribution=c.pct_contribution,
            )
            for c in result.contributions
        ]

        await self._risk_repo.save_var_result(result_record, contributions, session=session)

    async def _persist_stress_result(
        self,
        result: StressTestResult,
        scenario: StressScenario,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Persist stress test result and position impacts."""
        result_record = StressTestResultRecord(
            portfolio_id=str(result.portfolio_id),
            scenario_name=result.scenario_name,
            scenario_type=result.scenario_type,
            shocks=scenario.shocks,
            total_pnl_impact=result.total_pnl_impact,
            total_pct_change=result.total_pct_change,
            calculated_at=result.calculated_at,
        )

        impacts = [
            StressPositionImpactRecord(
                stress_result_id=result_record.id,
                instrument_id=imp.instrument_id,
                current_value=imp.current_value,
                stressed_value=imp.stressed_value,
                pnl_impact=imp.pnl_impact,
                pct_change=imp.pct_change,
            )
            for imp in result.position_impacts
        ]

        await self._risk_repo.save_stress_result(result_record, impacts, session=session)

    # ------------------------------------------------------------------
    # 3A. Counterparty & Credit Risk
    # ------------------------------------------------------------------

    async def get_counterparty_exposures(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[CounterpartyExposure]:
        """Get latest counterparty exposure for a portfolio."""
        records = await self._risk_repo.get_counterparty_exposures(
            portfolio_id,
            session=session,
        )
        cpty_map = await self._risk_repo.get_counterparty_map(session=session)
        return [
            CounterpartyExposure(
                counterparty_id=UUID(r.counterparty_id),
                counterparty_name=cpty_map.get(r.counterparty_id, "Unknown"),
                portfolio_id=UUID(r.portfolio_id),
                business_date=r.business_date,
                gross_exposure=r.gross_exposure,
                net_exposure=r.net_exposure,
                collateral_held=r.collateral_held,
                collateral_posted=r.collateral_posted,
                credit_limit=r.credit_limit,
                utilization_pct=r.utilization_pct,
                breach=r.breach,
            )
            for r in records
        ]

    async def list_counterparties(
        self, *, session: AsyncSession | None = None
    ) -> list[CounterpartyInfo]:
        records = await self._risk_repo.list_counterparties(session=session)
        return [
            CounterpartyInfo(
                id=UUID(r.id),
                name=r.name,
                counterparty_type=CounterpartyType(r.counterparty_type),
                credit_rating=r.credit_rating,
                credit_limit=r.credit_limit,
                netting_eligible=r.netting_eligible,
                is_active=r.is_active,
            )
            for r in records
        ]

    async def record_counterparty_exposure(
        self,
        *,
        counterparty_id: str,
        portfolio_id: UUID,
        business_date: datetime,
        gross_exposure: Decimal,
        net_exposure: Decimal,
        collateral_held: Decimal = ZERO,
        collateral_posted: Decimal = ZERO,
        session: AsyncSession | None = None,
    ) -> None:
        """Record or update counterparty exposure snapshot."""
        cpty = await self._risk_repo.get_counterparty(counterparty_id, session=session)
        credit_limit = cpty.credit_limit if cpty else ZERO
        util = net_exposure / credit_limit if credit_limit > 0 else Decimal(999)
        breach = net_exposure > credit_limit if credit_limit > 0 else False

        record = CounterpartyExposureRecord(
            id=str(uuid4()),
            counterparty_id=counterparty_id,
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            collateral_held=collateral_held,
            collateral_posted=collateral_posted,
            credit_limit=credit_limit,
            utilization_pct=util,
            breach=breach,
        )
        await self._risk_repo.save_counterparty_exposure(record, session=session)

        if breach:
            logger.warning(
                "counterparty_limit_breach",
                counterparty_id=counterparty_id,
                net_exposure=str(net_exposure),
                credit_limit=str(credit_limit),
            )

    # ------------------------------------------------------------------
    # 3B. Liquidity Risk
    # ------------------------------------------------------------------

    async def calculate_liquidity(
        self,
        portfolio_id: UUID,
        fund_slug: str | None = None,
        *,
        pending_redemptions: Decimal = ZERO,
        session: AsyncSession | None = None,
    ) -> LiquidityProfile:
        """Compute and persist liquidity risk profile."""
        positions = await self._position_service.get_positions(portfolio_id, session=session)
        if not positions:
            now = datetime.now(UTC)
            return LiquidityProfile(
                portfolio_id=portfolio_id,
                business_date=now,
                total_nav=ZERO,
                pct_1_day=ZERO,
                pct_1_week=ZERO,
                pct_1_month=ZERO,
                pct_3_months=ZERO,
                pct_illiquid=ZERO,
                weighted_days_to_liquidate=ZERO,
                redemption_coverage_pct=Decimal(1),
            )

        # Build position data with ADV estimates
        pos_data: list[tuple[str, Decimal, Decimal]] = []
        total_nav = ZERO
        for p in positions:
            mv = (
                p.market_value
                if hasattr(p, "market_value")
                else p.quantity * getattr(p, "current_price", ZERO)
            )
            total_nav += mv
            # Estimate ADV from security master or use a heuristic
            sec = await self._security_master_service.get_instrument(
                p.instrument_id,
                session=session,
            )
            adv = Decimal(str(getattr(sec, "avg_daily_volume", 0) or 0))
            # Convert ADV shares to USD
            price = getattr(p, "current_price", ZERO) or ZERO
            adv_usd = adv * price if price > 0 else adv
            pos_data.append((p.instrument_id, mv, adv_usd))

        now = datetime.now(UTC)
        profile, details = calculate_liquidity_profile(
            portfolio_id=portfolio_id,
            positions=pos_data,
            total_nav=total_nav,
            business_date=now,
            pending_redemptions=pending_redemptions,
        )

        # Persist
        record = LiquidityProfileRecord(
            id=str(uuid4()),
            portfolio_id=str(portfolio_id),
            business_date=now,
            total_nav=total_nav,
            pct_1_day=profile.pct_1_day,
            pct_1_week=profile.pct_1_week,
            pct_1_month=profile.pct_1_month,
            pct_3_months=profile.pct_3_months,
            pct_illiquid=profile.pct_illiquid,
            weighted_days_to_liquidate=profile.weighted_days_to_liquidate,
            redemption_coverage_pct=profile.redemption_coverage_pct,
            details=[
                {
                    "instrument_id": d.instrument_id,
                    "market_value": str(d.market_value),
                    "adv": str(d.avg_daily_volume_usd),
                    "days": str(d.days_to_liquidate),
                    "bucket": d.liquidity_bucket,
                }
                for d in details
            ],
        )
        await self._risk_repo.save_liquidity_profile(record, session=session)

        logger.info(
            "liquidity_profile_calculated",
            portfolio_id=str(portfolio_id),
            pct_illiquid=str(profile.pct_illiquid),
            days_to_liquidate=str(profile.weighted_days_to_liquidate),
        )
        return profile

    # ------------------------------------------------------------------
    # 3C. Margin Management
    # ------------------------------------------------------------------

    async def calculate_margin(
        self,
        portfolio_id: UUID,
        fund_slug: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> MarginSummary:
        """Compute and persist margin requirements."""
        positions = await self._position_service.get_positions(portfolio_id, session=session)

        pos_data: list[tuple[str, Decimal, str]] = []
        for p in positions:
            mv = (
                p.market_value
                if hasattr(p, "market_value")
                else p.quantity * getattr(p, "current_price", ZERO)
            )
            sec = await self._security_master_service.get_instrument(
                p.instrument_id,
                session=session,
            )
            asset_class = getattr(sec, "asset_class", "equity") or "equity"
            pos_data.append((p.instrument_id, mv, asset_class))

        # Get cash balance for margin available
        cash_balance = ZERO
        # Try to get from cash_management if available
        try:
            cash_svc = getattr(self, "_cash_service", None)
            if cash_svc:
                bal = await cash_svc.get_total_balance(portfolio_id, session=session)
                cash_balance = bal
        except Exception:
            # Estimate from position_service if cash not available
            nav = sum(abs(mv) for _, mv, _ in pos_data)
            cash_balance = nav * Decimal("0.6")  # Assume 60% equity/40% leverage

        now = datetime.now(UTC)
        summary, pos_margins = calculate_margin_requirements(
            portfolio_id=portfolio_id,
            positions=pos_data,
            cash_balance=cash_balance,
            business_date=now,
        )

        # Persist
        record = MarginRequirementRecord(
            id=str(uuid4()),
            portfolio_id=str(portfolio_id),
            business_date=now,
            initial_margin=summary.initial_margin,
            maintenance_margin=summary.maintenance_margin,
            margin_available=cash_balance,
            margin_excess_deficit=summary.margin_excess_deficit,
            margin_utilization_pct=summary.margin_utilization_pct,
            margin_call_triggered=summary.margin_call_triggered,
            details=[
                {
                    "instrument_id": m.instrument_id,
                    "market_value": str(m.market_value),
                    "margin_rate": str(m.margin_rate),
                    "initial_margin": str(m.initial_margin),
                }
                for m in pos_margins
            ],
        )
        await self._risk_repo.save_margin_requirement(record, session=session)

        if summary.margin_call_triggered:
            logger.warning(
                "margin_call_triggered",
                portfolio_id=str(portfolio_id),
                deficit=str(summary.margin_excess_deficit),
            )

        return summary
