"""Risk snapshot service — VaR, stress testing, factor decomposition, and snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import structlog

from app.modules.risk_engine.core.calculator import (
    calculate_factor_decomposition,
    calculate_historical_var,
    calculate_parametric_var,
    run_stress_test,
)
from app.modules.risk_engine.interfaces.snapshot import RiskSnapshot
from app.modules.risk_engine.interfaces.var import VaRMethod, VaRResult
from app.modules.risk_engine.models.risk_snapshot import RiskSnapshotRecord
from app.modules.risk_engine.models.stress_position_impact import StressPositionImpactRecord
from app.modules.risk_engine.models.stress_test_result import StressTestResultRecord
from app.modules.risk_engine.models.var_contribution import VaRContributionRecord
from app.modules.risk_engine.models.var_result import VaRResultRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.market_data.core.fx import FXConverter
    from app.modules.market_data.services import MarketDataService
    from app.modules.positions.services import PositionService
    from app.modules.risk_engine.interfaces.factor import FactorDecomposition
    from app.modules.risk_engine.interfaces.stress import StressScenario, StressTestResult
    from app.modules.risk_engine.repositories import (
        FactorExposureRepository,
        RiskSnapshotRepository,
        StressPositionImpactRepository,
        StressTestResultRepository,
        VaRContributionRepository,
        VaRResultRepository,
    )
    from app.modules.security_master.services import SecurityMasterService
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)
# Minimum number of price history days needed for VaR
MIN_HISTORY_DAYS = 30
# Default lookback window for historical VaR
DEFAULT_LOOKBACK = 252


class RiskSnapshotService:
    """Calculates portfolio risk metrics and manages risk snapshots."""

    def __init__(
        self,
        *,
        snapshot_repo: RiskSnapshotRepository,
        var_result_repo: VaRResultRepository,
        var_contribution_repo: VaRContributionRepository,
        stress_result_repo: StressTestResultRepository,
        stress_impact_repo: StressPositionImpactRepository,
        factor_repo: FactorExposureRepository,
        position_service: PositionService,
        market_data_service: MarketDataService,
        security_master_service: SecurityMasterService,
        event_bus: EventBus | None = None,
        fx_converter: FXConverter | None = None,
        base_currency: str = "USD",
        var_limit_pct: float = 5.0,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._var_result_repo = var_result_repo
        self._var_contribution_repo = var_contribution_repo
        self._stress_result_repo = stress_result_repo
        self._stress_impact_repo = stress_impact_repo
        self._factor_repo = factor_repo
        self._position_service = position_service
        self._market_data_service = market_data_service
        self._security_master_service = security_master_service
        self._event_bus = event_bus
        self._fx = fx_converter
        self._base_currency = base_currency
        self._var_limit_pct = var_limit_pct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_latest_snapshot(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> RiskSnapshot | None:
        record = await self._snapshot_repo.get_latest_snapshot(portfolio_id, session=session)
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
        records = await self._snapshot_repo.get_snapshot_history(
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

        logger.debug(
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

        logger.debug(
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

        instruments = await self._security_master_service.list_active(session=session)
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

        logger.debug(
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
        await self._snapshot_repo.insert_snapshot(record, session=session)
        await self._publish_risk_event(record, fund_slug)

        # Check VaR limit breach: if 95% 1-day VaR exceeds threshold % of NAV
        if nav > ZERO and record.var_95_1d:
            var_pct = float(record.var_95_1d / nav * 100)
            if var_pct > self._var_limit_pct:
                await self._publish_limit_breach(record, fund_slug, var_pct)

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
        instruments = await self._security_master_service.list_active(session=session)
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
        instruments = await self._security_master_service.list_active(session=session)
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

    async def _publish_limit_breach(
        self,
        record: RiskSnapshotRecord,
        fund_slug: str | None,
        var_pct: float,
    ) -> None:
        """Publish a risk.limit_breached event when VaR exceeds the threshold."""
        if self._event_bus is None or not fund_slug:
            return

        event = BaseEvent(
            event_type=AuditEventType.RISK_LIMIT_BREACHED,
            data={
                "portfolio_id": record.portfolio_id,
                "var_95_1d": str(record.var_95_1d),
                "nav": str(record.nav),
                "var_pct_of_nav": f"{var_pct:.2f}",
                "limit_pct": str(self._var_limit_pct),
                "breach_type": "var_95_1d",
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "risk.limit_breached"),
            event,
        )
        logger.warning(
            "risk_limit_breached",
            portfolio_id=record.portfolio_id,
            var_pct=f"{var_pct:.2f}",
            limit_pct=self._var_limit_pct,
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

        await self._var_result_repo.insert_var_result(result_record, session=session)

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

        await self._var_contribution_repo.insert_contributions(contributions, session=session)

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

        await self._stress_result_repo.insert_stress_result(result_record, session=session)

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

        await self._stress_impact_repo.insert_impacts(impacts, session=session)
