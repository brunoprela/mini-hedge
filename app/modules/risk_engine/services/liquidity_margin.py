"""Liquidity and margin risk service — liquidity profiles and margin requirements."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.risk_engine.core.calculator import (
    calculate_liquidity_profile,
    calculate_margin_requirements,
)
from app.modules.risk_engine.interfaces.liquidity import LiquidityProfile
from app.modules.risk_engine.models.liquidity_profile import LiquidityProfileRecord
from app.modules.risk_engine.models.margin_requirement import MarginRequirementRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.positions.services import PositionService
    from app.modules.risk_engine.interfaces.margin import MarginSummary
    from app.modules.risk_engine.repositories import (
        LiquidityRepository,
        MarginRepository,
    )
    from app.modules.security_master.services import SecurityMasterService

logger = structlog.get_logger()

ZERO = Decimal(0)


class LiquidityMarginService:
    """Computes and persists liquidity and margin risk metrics."""

    def __init__(
        self,
        *,
        liquidity_repo: LiquidityRepository,
        margin_repo: MarginRepository,
        position_service: PositionService,
        security_master_service: SecurityMasterService,
    ) -> None:
        self._liquidity_repo = liquidity_repo
        self._margin_repo = margin_repo
        self._position_service = position_service
        self._security_master_service = security_master_service

    # ------------------------------------------------------------------
    # Public API
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
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
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
            sec = await self._security_master_service.get_by_ticker(
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
        await self._liquidity_repo.save_liquidity_profile(record, session=session)

        logger.info(
            "liquidity_profile_calculated",
            portfolio_id=str(portfolio_id),
            pct_illiquid=str(profile.pct_illiquid),
            days_to_liquidate=str(profile.weighted_days_to_liquidate),
        )
        return profile

    async def calculate_margin(
        self,
        portfolio_id: UUID,
        fund_slug: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> MarginSummary:
        """Compute and persist margin requirements."""
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)

        pos_data: list[tuple[str, Decimal, str]] = []
        for p in positions:
            mv = (
                p.market_value
                if hasattr(p, "market_value")
                else p.quantity * getattr(p, "current_price", ZERO)
            )
            sec = await self._security_master_service.get_by_ticker(
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
        await self._margin_repo.save_margin_requirement(record, session=session)

        if summary.margin_call_triggered:
            logger.warning(
                "margin_call_triggered",
                portfolio_id=str(portfolio_id),
                deficit=str(summary.margin_excess_deficit),
            )

        return summary
