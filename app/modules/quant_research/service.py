"""Quant research service — factor analysis and regime detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.quant_research.interface import (
    FactorAnalysisResult,
    FactorDefinition,
    FactorExposure,
    FactorType,
    MarketRegime,
    PortfolioFactorDecomposition,
    RegimeAnalysis,
    RegimeType,
)
from app.modules.quant_research.models import (
    FactorDefinitionRecord,
    FactorExposureRecord,
    RegimeSnapshotRecord,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.quant_research.regime_detector import RegimeDetector
    from app.modules.quant_research.repository import (
        FactorRepository,
        RegimeRepository,
    )
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)


class QuantResearchService:
    """Orchestrates factor research and regime detection."""

    def __init__(
        self,
        factor_repo: FactorRepository,
        regime_repo: RegimeRepository,
        factor_engine_fns: dict[str, Callable[..., dict[str, Decimal]]],
        regime_detector: RegimeDetector,
        session_factory: TenantSessionFactory,
        event_bus: EventBus | None = None,
    ) -> None:
        self._factor_repo = factor_repo
        self._regime_repo = regime_repo
        self._factor_fns = factor_engine_fns
        self._regime_detector = regime_detector
        self._session_factory = session_factory
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Factor Research
    # ------------------------------------------------------------------

    async def create_factor(
        self,
        name: str,
        factor_type: FactorType,
        description: str | None = None,
        formula: str | None = None,
        parameters: dict | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> FactorDefinition:
        record = FactorDefinitionRecord(
            name=name,
            factor_type=factor_type.value,
            description=description or "",
            formula=formula or "",
            parameters=parameters,
            is_active=True,
        )
        await self._factor_repo.create_factor(record, session=session)
        return FactorDefinition(
            id=UUID(record.id),
            name=record.name,
            factor_type=FactorType(record.factor_type),
            description=record.description or "",
            formula=record.formula or "",
            parameters=record.parameters or {},
            is_active=record.is_active,
        )

    async def list_factors(self, *, session: AsyncSession | None = None) -> list[FactorDefinition]:
        records = await self._factor_repo.list_factors(session=session)
        return [
            FactorDefinition(
                id=UUID(r.id),
                name=r.name,
                factor_type=FactorType(r.factor_type),
                description=r.description or "",
                formula=r.formula or "",
                parameters=r.parameters or {},
                is_active=r.is_active,
            )
            for r in records
        ]

    async def compute_factor_exposures(
        self,
        factor_name: str,
        price_data: dict[str, list[tuple[date, Decimal]]],
        *,
        session: AsyncSession | None = None,
    ) -> list[FactorExposure]:
        factor_record = await self._factor_repo.get_by_name(factor_name, session=session)
        if factor_record is None:
            msg = f"Factor '{factor_name}' not found"
            raise ValueError(msg)

        compute_fn = self._factor_fns.get(factor_record.factor_type)
        if compute_fn is None:
            msg = f"No compute function for factor type '{factor_record.factor_type}'"
            raise ValueError(msg)

        raw_exposures = compute_fn(price_data)
        today = date.today()

        exposure_records = [
            FactorExposureRecord(
                factor_id=factor_record.id,
                instrument_id=inst_id,
                exposure=exp,
                z_score=exp,
                as_of_date=today,
            )
            for inst_id, exp in raw_exposures.items()
        ]
        await self._factor_repo.save_exposures(exposure_records, session=session)

        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.FACTOR_EXPOSURE_COMPUTED,
                    data={
                        "factor_name": factor_name,
                        "factor_id": factor_record.id,
                        "instrument_count": len(raw_exposures),
                        "as_of_date": str(today),
                    },
                ),
            )

        return [
            FactorExposure(
                factor_name=factor_name,
                instrument_id=inst_id,
                exposure=exp,
                z_score=exp,
                as_of_date=today,
            )
            for inst_id, exp in raw_exposures.items()
        ]

    async def analyze_factor(
        self,
        factor_name: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> FactorAnalysisResult:
        factor_record = await self._factor_repo.get_by_name(factor_name, session=session)
        if factor_record is None:
            msg = f"Factor '{factor_name}' not found"
            raise ValueError(msg)

        returns = await self._factor_repo.get_returns(
            factor_record.id,
            start_date=start_date,
            end_date=end_date,
            session=session,
        )

        if not returns:
            today = date.today()
            return FactorAnalysisResult(
                factor_name=factor_name,
                start_date=start_date or today,
                end_date=end_date or today,
                mean_return=ZERO,
                volatility=ZERO,
                sharpe_ratio=ZERO,
                max_drawdown=ZERO,
                correlation_matrix={},
                top_exposures=[],
            )

        return_values = [r.return_pct for r in returns]
        mean_ret = sum(return_values) / Decimal(len(return_values))

        import statistics as stats

        vol = (
            Decimal(str(stats.stdev(float(v) for v in return_values)))
            if len(return_values) > 1
            else ZERO
        )
        ann_factor = Decimal("15.8745")  # sqrt(252)
        ann_vol = vol * ann_factor
        ann_mean = mean_ret * Decimal(252)
        risk_free = Decimal("0.04")
        sharpe = (ann_mean - risk_free) / ann_vol if ann_vol != ZERO else ZERO

        # Max drawdown from cumulative returns
        cum_values = [r.cumulative_return for r in returns]
        peak = ZERO
        max_dd = ZERO
        for cv in cum_values:
            if cv > peak:
                peak = cv
            dd = (cv - peak) / peak if peak != ZERO else ZERO
            if dd < max_dd:
                max_dd = dd

        actual_start = returns[0].return_date
        actual_end = returns[-1].return_date

        # Cross-factor correlation — gather returns for all active factors
        from app.modules.quant_research.factor_engine import (
            compute_factor_correlation,
        )

        all_factors = await self._factor_repo.list_factors(session=session)
        factor_return_series: dict[str, list[Decimal]] = {}
        for f in all_factors:
            f_returns = await self._factor_repo.get_returns(
                f.id, start_date=start_date, end_date=end_date, session=session
            )
            if f_returns:
                factor_return_series[f.name] = [r.return_pct for r in f_returns]

        corr_matrix: dict[str, dict[str, float]] = {}
        if len(factor_return_series) >= 2:
            corr_matrix = compute_factor_correlation(factor_return_series)

        # Top exposures — latest exposures sorted by absolute z-score
        top_exposures: list[FactorExposure] = []
        today = date.today()
        exp_records = await self._factor_repo.get_exposures(
            factor_record.id, today, session=session
        )
        sorted_exps = sorted(exp_records, key=lambda e: abs(e.z_score), reverse=True)
        for e in sorted_exps[:10]:
            top_exposures.append(
                FactorExposure(
                    factor_name=factor_name,
                    instrument_id=e.instrument_id,
                    exposure=e.exposure,
                    z_score=e.z_score,
                    as_of_date=e.as_of_date,
                )
            )

        return FactorAnalysisResult(
            factor_name=factor_name,
            start_date=actual_start,
            end_date=actual_end,
            mean_return=ann_mean,
            volatility=ann_vol,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            correlation_matrix=corr_matrix,
            top_exposures=top_exposures,
        )

    async def decompose_portfolio(
        self,
        portfolio_weights: dict[str, Decimal],
        factor_names: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> PortfolioFactorDecomposition:
        from app.modules.quant_research.factor_engine import (
            decompose_portfolio as _decompose,
        )

        factor_exposures: dict[str, dict[str, Decimal]] = {}
        for fname in factor_names:
            factor_record = await self._factor_repo.get_by_name(fname, session=session)
            if factor_record is None:
                continue
            today = date.today()
            exp_records = await self._factor_repo.get_exposures(
                factor_record.id, today, session=session
            )
            factor_exposures[fname] = {r.instrument_id: r.exposure for r in exp_records}

        contributions, residual = _decompose(portfolio_weights, factor_exposures)

        today = date.today()
        factors = [
            FactorExposure(
                factor_name=fname,
                instrument_id="portfolio",
                exposure=contrib,
                z_score=ZERO,
                as_of_date=today,
            )
            for fname, contrib in contributions.items()
        ]

        explained = Decimal(1) - residual

        return PortfolioFactorDecomposition(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000000"),
            as_of_date=today,
            factors=factors,
            explained_variance_pct=explained,
            residual_pct=residual,
        )

    # ------------------------------------------------------------------
    # Regime Detection
    # ------------------------------------------------------------------

    async def detect_regime(
        self,
        market_prices: list[tuple[date, Decimal]],
        *,
        session: AsyncSession | None = None,
    ) -> RegimeAnalysis:
        analysis = self._regime_detector.detect_regime(market_prices)

        # Persist snapshot
        indicators_json = {ind.name: str(ind.value) for ind in analysis.indicators}
        record = RegimeSnapshotRecord(
            regime_type=analysis.current_regime.value,
            detection_method=self._regime_detector._config.method.value,
            confidence=analysis.confidence,
            indicators=indicators_json,
            start_date=date.today(),
            end_date=None,
        )
        await self._regime_repo.save_snapshot(record, session=session)

        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.REGIME_DETECTED,
                    data={
                        "regime_type": analysis.current_regime.value,
                        "confidence": str(analysis.confidence),
                        "detection_method": self._regime_detector._config.method.value,
                        "snapshot_id": record.id,
                    },
                ),
            )

        return analysis

    async def get_regime_history(
        self, *, limit: int = 100, session: AsyncSession | None = None
    ) -> list[MarketRegime]:
        records = await self._regime_repo.get_history(limit=limit, session=session)
        return [
            MarketRegime(
                regime_type=RegimeType(r.regime_type),
                start_date=r.start_date,
                end_date=r.end_date,
                confidence=r.confidence,
                indicators={k: Decimal(v) for k, v in (r.indicators or {}).items()},
            )
            for r in records
        ]

    async def get_current_regime(
        self, *, session: AsyncSession | None = None
    ) -> MarketRegime | None:
        record = await self._regime_repo.get_latest(session=session)
        if record is None:
            return None
        return MarketRegime(
            regime_type=RegimeType(record.regime_type),
            start_date=record.start_date,
            end_date=record.end_date,
            confidence=record.confidence,
            indicators={k: Decimal(v) for k, v in (record.indicators or {}).items()},
        )
