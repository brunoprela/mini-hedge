"""Risk engine service — calculates and persists risk metrics."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import structlog

from app.modules.risk_engine.calculator import (
    calculate_factor_decomposition,
    calculate_historical_var,
    calculate_parametric_var,
    run_stress_test,
)
from app.modules.risk_engine.interface import (
    FactorDecomposition,
    RiskSnapshot,
    StressScenario,
    StressTestResult,
    VaRMethod,
    VaRResult,
)
from app.modules.risk_engine.models import (
    RiskSnapshotRecord,
    StressPositionImpactRecord,
    StressTestResultRecord,
    VaRContributionRecord,
    VaRResultRecord,
)
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
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
    ) -> None:
        self._repo = risk_repo
        self._positions = position_service
        self._market_data = market_data_service
        self._sm = security_master_service
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_latest_snapshot(self, portfolio_id: UUID) -> RiskSnapshot | None:
        record = await self._repo.get_latest_snapshot(portfolio_id)
        if record is None:
            return None
        return RiskSnapshot(
            id=record.id,
            portfolio_id=record.portfolio_id,
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
    ) -> list[RiskSnapshot]:
        records = await self._repo.get_snapshot_history(portfolio_id, start, end)
        return [
            RiskSnapshot(
                id=r.id,
                portfolio_id=r.portfolio_id,
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
    ) -> VaRResult:
        """Calculate VaR for a portfolio."""
        weights, returns_matrix, instrument_ids, nav = await self._build_risk_inputs(portfolio_id)

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
        await self._persist_var_result(result)

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
    ) -> StressTestResult:
        """Run a stress test scenario on a portfolio."""
        positions_data, nav = await self._build_stress_inputs(portfolio_id)

        result = run_stress_test(portfolio_id, scenario, positions_data, nav)

        # Persist
        await self._persist_stress_result(result, scenario)

        logger.info(
            "stress_test_run",
            portfolio_id=str(portfolio_id),
            scenario=scenario.name,
            impact=str(result.total_pnl_impact),
        )
        return result

    async def calculate_factor_model(self, portfolio_id: UUID) -> FactorDecomposition:
        """Calculate factor decomposition for a portfolio."""
        weights, returns_matrix, instrument_ids, nav = await self._build_risk_inputs(portfolio_id)

        instruments = await self._sm.get_all_active()
        sector_lookup = {i.ticker: i.sector or "Unknown" for i in instruments}
        sector_map = {iid: sector_lookup.get(iid, "Unknown") for iid in instrument_ids}

        result = calculate_factor_decomposition(
            portfolio_id,
            weights,
            returns_matrix,
            instrument_ids,
            sector_map,
            nav,
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
    ) -> RiskSnapshot:
        """Calculate and persist a complete risk snapshot."""
        # Run independent calculations concurrently
        var_95, var_99, positions = await asyncio.gather(
            self.calculate_var(portfolio_id, VaRMethod.HISTORICAL, 0.95, 1),
            self.calculate_var(portfolio_id, VaRMethod.HISTORICAL, 0.99, 1),
            self._positions.get_by_portfolio(portfolio_id),
        )
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
        await self._repo.save_snapshot(record)
        await self._publish_risk_event(record, fund_slug)

        return RiskSnapshot(
            id=record.id,
            portfolio_id=record.portfolio_id,
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
        self, portfolio_id: UUID
    ) -> tuple[dict[str, float], np.ndarray, list[str], float]:  # type: ignore[type-arg]
        """Build weights, returns matrix, instrument list, and NAV."""
        positions = await self._positions.get_by_portfolio(portfolio_id)
        positions = [p for p in positions if p.quantity != ZERO]

        if not positions:
            return {}, np.empty((0, 0)), [], 0.0

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))
        if nav == 0:
            return {}, np.empty((0, 0)), [], 0.0

        instrument_ids = [p.instrument_id for p in positions]
        weights = {
            p.instrument_id: float(p.market_value) / nav for p in positions if p.market_value
        }

        # Build returns matrix from price history
        returns_matrix = await self._build_returns_matrix(instrument_ids)

        return weights, returns_matrix, instrument_ids, nav

    async def _build_returns_matrix(self, instrument_ids: list[str]) -> np.ndarray:  # type: ignore[type-arg]
        """Build a (n_days, n_instruments) returns matrix.

        Uses synthetic returns based on instrument reference data (annual_drift,
        annual_volatility) until real price history is available.
        """
        n = len(instrument_ids)
        if n == 0:
            return np.empty((0, 0))

        # Look up drift/volatility from instrument reference data
        instruments = await self._sm.get_all_active()
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
            daily_returns[:, i] = np.random.normal(daily_drift, daily_vol, n_days)

        return daily_returns

    async def _build_stress_inputs(
        self, portfolio_id: UUID
    ) -> tuple[dict[str, tuple[Decimal, str | None]], float]:
        """Build position data for stress testing."""
        positions = await self._positions.get_by_portfolio(portfolio_id)
        positions = [p for p in positions if p.quantity != ZERO]

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))

        # Batch-fetch instruments instead of N+1
        instruments = await self._sm.get_all_active()
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
            event_type="risk.updated",
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

    async def _persist_var_result(self, result: VaRResult) -> None:
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

        await self._repo.save_var_result(result_record, contributions)

    async def _persist_stress_result(
        self,
        result: StressTestResult,
        scenario: StressScenario,
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

        await self._repo.save_stress_result(result_record, impacts)
