"""Performance attribution service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import structlog

from app.modules.attribution.calculator import (
    calculate_brinson_fachler,
    calculate_risk_based_attribution,
    link_multi_period,
)
from app.modules.attribution.interface import (
    BrinsonFachlerResult,
    CumulativeAttribution,
    RiskBasedResult,
    SectorAttribution,
)
from app.modules.attribution.models import (
    BrinsonFachlerRecord,
    BrinsonFachlerSectorRecord,
    RiskBasedRecord,
    RiskFactorContributionRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.attribution.repository import AttributionRepository
    from app.modules.positions.service import PositionService
    from app.modules.security_master.service import SecurityMasterService

logger = structlog.get_logger()

ZERO = Decimal(0)


class AttributionService:
    """Calculates and persists performance attribution."""

    def __init__(
        self,
        *,
        attribution_repo: AttributionRepository,
        position_service: PositionService,
        security_master_service: SecurityMasterService,
    ) -> None:
        self._attribution_repo = attribution_repo
        self._position_service = position_service
        self._security_master_service = security_master_service

    async def calculate_brinson_fachler(
        self,
        portfolio_id: UUID,
        period_start: date,
        period_end: date,
        *,
        session: AsyncSession | None = None,
    ) -> BrinsonFachlerResult:
        """Calculate Brinson-Fachler attribution for a period."""
        all_positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        instruments = await self._security_master_service.get_all_active(session=session)
        positions = [p for p in all_positions if p.quantity != ZERO]

        if not positions:
            return BrinsonFachlerResult(
                portfolio_id=portfolio_id,
                period_start=period_start,
                period_end=period_end,
                portfolio_return=ZERO,
                benchmark_return=ZERO,
                active_return=ZERO,
                total_allocation=ZERO,
                total_selection=ZERO,
                total_interaction=ZERO,
                sectors=[],
                calculated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))
        instrument_ids = [p.instrument_id for p in positions]

        # Build weights and sector map
        portfolio_weights: dict[str, float] = {}
        sector_map: dict[str, str] = {}
        sector_lookup = {i.ticker: i.sector or "Unknown" for i in instruments}

        for p in positions:
            w = float(p.market_value) / nav if nav > 0 else 0.0
            portfolio_weights[p.instrument_id] = w
            sector_map[p.instrument_id] = sector_lookup.get(p.instrument_id, "Unknown")

        # Equal-weight benchmark (simplification — use market-cap in production)
        n = len(instrument_ids)
        benchmark_weights = {iid: 1.0 / n for iid in instrument_ids}

        # Synthetic returns for the period
        returns = await self._generate_synthetic_returns(instrument_ids, session=session)
        portfolio_returns = dict(zip(instrument_ids, returns, strict=True))
        benchmark_returns = portfolio_returns  # same returns, different weights

        result = calculate_brinson_fachler(
            portfolio_id,
            period_start,
            period_end,
            portfolio_weights,
            benchmark_weights,
            portfolio_returns,
            benchmark_returns,
            sector_map,
        )

        # Persist
        await self._persist_brinson_fachler(result, session=session)

        logger.info(
            "brinson_fachler_calculated",
            portfolio_id=str(portfolio_id),
            active_return=str(result.active_return),
        )
        return result

    async def calculate_risk_based(
        self,
        portfolio_id: UUID,
        period_start: date,
        period_end: date,
        *,
        session: AsyncSession | None = None,
    ) -> RiskBasedResult:
        """Calculate risk-based P&L attribution."""
        all_positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        instruments = await self._security_master_service.get_all_active(session=session)
        positions = [p for p in all_positions if p.quantity != ZERO]

        if not positions:
            return RiskBasedResult(
                portfolio_id=portfolio_id,
                period_start=period_start,
                period_end=period_end,
                total_pnl=ZERO,
                systematic_pnl=ZERO,
                idiosyncratic_pnl=ZERO,
                systematic_pct=ZERO,
                factor_contributions=[],
                calculated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))
        instrument_ids = [p.instrument_id for p in positions]

        weights = {
            p.instrument_id: float(p.market_value) / nav
            for p in positions
            if p.market_value and nav > 0
        }
        sector_lookup = {i.ticker: i.sector or "Unknown" for i in instruments}
        sector_map = {iid: sector_lookup.get(iid, "Unknown") for iid in instrument_ids}

        # Build returns matrix from instrument reference data
        returns_matrix = await self._build_returns_matrix(instrument_ids, session=session)

        result = calculate_risk_based_attribution(
            portfolio_id,
            period_start,
            period_end,
            weights,
            returns_matrix,
            instrument_ids,
            sector_map,
            nav,
        )

        # Persist
        await self._persist_risk_based(result, session=session)

        logger.info(
            "risk_based_attribution_calculated",
            portfolio_id=str(portfolio_id),
            systematic_pct=str(result.systematic_pct),
        )
        return result

    async def calculate_cumulative(
        self,
        portfolio_id: UUID,
        period_start: date,
        period_end: date,
        *,
        session: AsyncSession | None = None,
    ) -> CumulativeAttribution:
        """Calculate multi-period cumulative attribution using Carino linking."""
        # Get stored single-period results
        records = await self._attribution_repo.get_brinson_fachler(
            portfolio_id, period_start, period_end, session=session
        )

        period_results: list[BrinsonFachlerResult] = []
        for r in records:
            sectors_records = await self._attribution_repo.get_bf_sectors(r.id, session=session)
            sectors = [
                SectorAttribution(
                    sector=s.sector,
                    portfolio_weight=s.portfolio_weight,
                    benchmark_weight=s.benchmark_weight,
                    portfolio_return=s.portfolio_return,
                    benchmark_return=s.benchmark_return,
                    allocation_effect=s.allocation_effect,
                    selection_effect=s.selection_effect,
                    interaction_effect=s.interaction_effect,
                    total_effect=s.total_effect,
                )
                for s in sectors_records
            ]
            period_results.append(
                BrinsonFachlerResult(
                    id=r.id,
                    portfolio_id=r.portfolio_id,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    portfolio_return=r.portfolio_return,
                    benchmark_return=r.benchmark_return,
                    active_return=r.active_return,
                    total_allocation=r.total_allocation,
                    total_selection=r.total_selection,
                    total_interaction=r.total_interaction,
                    sectors=sectors,
                    calculated_at=r.calculated_at,
                )
            )

        # If no stored periods, calculate a single period
        if not period_results:
            single = await self.calculate_brinson_fachler(
                portfolio_id, period_start, period_end, session=session
            )
            period_results = [single]

        result = link_multi_period(portfolio_id, period_start, period_end, period_results)

        logger.info(
            "cumulative_attribution_calculated",
            portfolio_id=str(portfolio_id),
            periods=len(period_results),
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_synthetic_returns(
        self,
        instrument_ids: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> list[float]:
        """Generate synthetic period returns from instrument reference data."""
        instruments = await self._security_master_service.get_all_active(session=session)
        drift_map = {i.ticker: i.annual_drift for i in instruments if i.annual_drift is not None}
        vol_map = {
            i.ticker: i.annual_volatility for i in instruments if i.annual_volatility is not None
        }

        returns = []
        for iid in instrument_ids:
            drift = drift_map.get(iid, 0.08) / 12  # monthly
            vol = vol_map.get(iid, 0.25) / np.sqrt(12)
            ret = float(np.random.normal(drift, vol))
            returns.append(ret)
        return returns

    async def _build_returns_matrix(
        self,
        instrument_ids: list[str],
        n_days: int = 252,
        *,
        session: AsyncSession | None = None,
    ) -> np.ndarray:  # type: ignore[type-arg]
        """Build synthetic returns matrix from instrument reference data."""
        instruments = await self._security_master_service.get_all_active(session=session)
        vol_map = {
            i.ticker: i.annual_volatility for i in instruments if i.annual_volatility is not None
        }
        drift_map = {i.ticker: i.annual_drift for i in instruments if i.annual_drift is not None}

        n = len(instrument_ids)
        matrix = np.zeros((n_days, n))
        for idx, iid in enumerate(instrument_ids):
            daily_vol = vol_map.get(iid, 0.25) / np.sqrt(252)
            daily_drift = drift_map.get(iid, 0.08) / 252
            matrix[:, idx] = np.random.normal(daily_drift, daily_vol, n_days)
        return matrix

    async def _persist_brinson_fachler(
        self, result: BrinsonFachlerResult, *, session: AsyncSession | None = None
    ) -> None:
        record = BrinsonFachlerRecord(
            portfolio_id=str(result.portfolio_id),
            period_start=result.period_start,
            period_end=result.period_end,
            portfolio_return=result.portfolio_return,
            benchmark_return=result.benchmark_return,
            active_return=result.active_return,
            total_allocation=result.total_allocation,
            total_selection=result.total_selection,
            total_interaction=result.total_interaction,
            calculated_at=result.calculated_at,
        )

        sectors = [
            BrinsonFachlerSectorRecord(
                bf_result_id=record.id,
                sector=s.sector,
                portfolio_weight=s.portfolio_weight,
                benchmark_weight=s.benchmark_weight,
                portfolio_return=s.portfolio_return,
                benchmark_return=s.benchmark_return,
                allocation_effect=s.allocation_effect,
                selection_effect=s.selection_effect,
                interaction_effect=s.interaction_effect,
                total_effect=s.total_effect,
            )
            for s in result.sectors
        ]

        await self._attribution_repo.save_brinson_fachler(record, sectors, session=session)

    async def _persist_risk_based(
        self, result: RiskBasedResult, *, session: AsyncSession | None = None
    ) -> None:
        record = RiskBasedRecord(
            portfolio_id=str(result.portfolio_id),
            period_start=result.period_start,
            period_end=result.period_end,
            total_pnl=result.total_pnl,
            systematic_pnl=result.systematic_pnl,
            idiosyncratic_pnl=result.idiosyncratic_pnl,
            systematic_pct=result.systematic_pct,
            calculated_at=result.calculated_at,
        )

        factors = [
            RiskFactorContributionRecord(
                rb_result_id=record.id,
                factor=f.factor,
                factor_return=f.factor_return,
                portfolio_exposure=f.portfolio_exposure,
                pnl_contribution=f.pnl_contribution,
                pct_of_total=f.pct_of_total,
            )
            for f in result.factor_contributions
        ]

        await self._attribution_repo.save_risk_based(record, factors, session=session)
