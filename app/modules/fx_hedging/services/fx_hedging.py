"""FX hedging service — forward lifecycle, MTM, hedge recommendations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.fx_hedging.core.calculator import (
    calculate_forward_rate,
    calculate_roll_cost,
    identify_expiring_forwards,
    mark_to_market_forward,
    recommend_hedges,
)
from app.modules.fx_hedging.interfaces import (
    FXForwardContract,
    FXForwardCreate,
    FXForwardStatus,
    FXHedgingSummary,
    HedgeRecommendationResponse,
    RollRecommendation,
)
from app.modules.fx_hedging.models.fx_forward import FXForwardRecord
from app.modules.fx_hedging.models.fx_interest_rate import FXInterestRateRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.fx_hedging.repositories import (
        FXForwardRepository,
        FXInterestRateRepository,
    )
    from app.modules.market_data.core.fx import FXConverter
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)
ONE = Decimal(1)


class FXHedgingService:
    """Manages FX forward contracts and hedging recommendations."""

    def __init__(
        self,
        *,
        forward_repo: FXForwardRepository,
        rate_repo: FXInterestRateRepository,
        event_bus: EventBus | None = None,
        fx_converter: FXConverter | None = None,
        base_currency: str = "USD",
    ) -> None:
        self._forward_repo = forward_repo
        self._rate_repo = rate_repo
        self._event_bus = event_bus
        self._fx = fx_converter
        self._base_currency = base_currency

    # -- Forward lifecycle -------------------------------------------------

    async def open_forward(
        self,
        create: FXForwardCreate,
        *,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> FXForwardContract:
        """Open a new FX forward contract (OTC — no exchange routing)."""
        record = FXForwardRecord(
            portfolio_id=str(create.portfolio_id),
            base_currency=create.base_currency,
            quote_currency=create.quote_currency,
            direction=create.direction,
            notional=create.notional,
            contract_rate=create.contract_rate,
            spot_at_inception=create.spot_at_inception,
            trade_date=create.trade_date,
            maturity_date=create.maturity_date,
            status=FXForwardStatus.OPEN,
            counterparty=create.counterparty,
        )
        record = await self._forward_repo.insert(record, session=session)
        logger.info(
            "fx_forward_opened",
            forward_id=record.id,
            pair=f"{create.base_currency}/{create.quote_currency}",
            notional=str(create.notional),
            direction=create.direction,
        )
        await self._publish_event(
            AuditEventType.FX_FORWARD_OPENED,
            fund_slug,
            {
                "forward_id": record.id,
                "base_currency": create.base_currency,
                "quote_currency": create.quote_currency,
                "notional": str(create.notional),
                "direction": create.direction,
                "contract_rate": str(create.contract_rate),
                "maturity_date": create.maturity_date.isoformat(),
            },
        )
        return self._to_contract(record)

    async def close_forward(
        self,
        forward_id: UUID,
        close_rate: Decimal,
        close_spot: Decimal,
        *,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> FXForwardContract:
        """Close an open forward contract."""
        record = await self._forward_repo.get_by_id(forward_id, session=session)
        if record is None:
            msg = f"Forward {forward_id} not found"
            raise ValueError(msg)
        if record.status != FXForwardStatus.OPEN:
            msg = f"Forward {forward_id} is {record.status}, cannot close"
            raise ValueError(msg)

        sign = ONE if record.direction == "buy" else -ONE
        realized_pnl = sign * record.notional * (close_rate - record.contract_rate)
        now = datetime.now(UTC)

        await self._forward_repo.update_status(
            forward_id,
            FXForwardStatus.CLOSED,
            close_rate=close_rate,
            close_spot=close_spot,
            closed_at=now,
            realized_pnl=realized_pnl.quantize(Decimal("0.01")),
            session=session,
        )
        logger.info(
            "fx_forward_closed",
            forward_id=str(forward_id),
            realized_pnl=str(realized_pnl),
        )
        await self._publish_event(
            AuditEventType.FX_FORWARD_CLOSED,
            fund_slug,
            {
                "forward_id": str(forward_id),
                "close_rate": str(close_rate),
                "realized_pnl": str(realized_pnl),
            },
        )
        # Re-fetch to return updated state
        updated = await self._forward_repo.get_by_id(forward_id, session=session)
        return self._to_contract(updated)  # type: ignore[arg-type]

    async def roll_forward(
        self,
        forward_id: UUID,
        new_maturity_date: date,
        new_contract_rate: Decimal,
        current_spot: Decimal,
        *,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> FXForwardContract:
        """Roll a forward: close existing + open new with roll_from_id audit trail."""
        record = await self._forward_repo.get_by_id(forward_id, session=session)
        if record is None:
            msg = f"Forward {forward_id} not found"
            raise ValueError(msg)

        # Close the existing forward at the current forward rate
        close_fwd = calculate_forward_rate(
            current_spot,
            await self._get_domestic_rate(session=session),
            await self._get_rate_for_currency(record.base_currency, session=session),
            max((date.fromisoformat(str(record.maturity_date)) - date.today()).days, 0),
        )
        await self.close_forward(
            forward_id,
            close_rate=close_fwd.forward,
            close_spot=current_spot,
            fund_slug=fund_slug,
            session=session,
        )
        # Mark as rolled (not just closed)
        await self._forward_repo.update_status(
            forward_id,
            FXForwardStatus.ROLLED,
            session=session,
        )

        # Open new forward with roll audit trail
        new_record = FXForwardRecord(
            portfolio_id=record.portfolio_id,
            base_currency=record.base_currency,
            quote_currency=record.quote_currency,
            direction=record.direction,
            notional=record.notional,
            contract_rate=new_contract_rate,
            spot_at_inception=current_spot,
            trade_date=date.today(),
            maturity_date=new_maturity_date,
            status=FXForwardStatus.OPEN,
            counterparty=record.counterparty,
            roll_from_id=str(forward_id),
        )
        new_record = await self._forward_repo.insert(new_record, session=session)
        logger.info(
            "fx_forward_rolled",
            old_forward_id=str(forward_id),
            new_forward_id=new_record.id,
            new_maturity=new_maturity_date.isoformat(),
        )
        await self._publish_event(
            AuditEventType.FX_FORWARD_ROLLED,
            fund_slug,
            {
                "old_forward_id": str(forward_id),
                "new_forward_id": new_record.id,
                "new_maturity_date": new_maturity_date.isoformat(),
                "new_contract_rate": str(new_contract_rate),
            },
        )
        return self._to_contract(new_record)

    # -- Mark-to-market ----------------------------------------------------

    async def mark_to_market_all(
        self,
        portfolio_id: UUID,
        *,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[FXForwardContract]:
        """MTM all open forwards for a portfolio."""
        forwards = await self._forward_repo.get_open_by_portfolio(
            portfolio_id,
            session=session,
        )
        now = datetime.now(UTC)
        today = date.today()
        results: list[FXForwardContract] = []

        domestic_rate = await self._get_domestic_rate(session=session)

        for fwd in forwards:
            remaining = max((fwd.maturity_date - today).days, 0)
            spot = self._get_spot(fwd.base_currency, fwd.quote_currency)
            if spot is None:
                pair = f"{fwd.base_currency}/{fwd.quote_currency}"
                logger.warning("fx_mtm_no_spot", forward_id=fwd.id, pair=pair)
                results.append(self._to_contract(fwd))
                continue

            foreign_rate = await self._get_rate_for_currency(
                fwd.base_currency,
                session=session,
            )
            mtm = mark_to_market_forward(
                contract_rate=fwd.contract_rate,
                contract_notional=fwd.notional,
                contract_direction=fwd.direction,
                current_spot=spot,
                domestic_rate=domestic_rate,
                foreign_rate=foreign_rate,
                remaining_days=remaining,
                quote_currency=fwd.quote_currency,
            )
            await self._forward_repo.update_mtm(
                UUID(fwd.id),
                mtm.mtm_value,
                now,
                session=session,
            )
            fwd.mtm_value = mtm.mtm_value
            fwd.mtm_timestamp = now
            results.append(self._to_contract(fwd))

        logger.info(
            "fx_forwards_mtm_complete",
            portfolio_id=str(portfolio_id),
            count=len(results),
        )
        await self._publish_event(
            AuditEventType.FX_FORWARD_MTM,
            fund_slug,
            {
                "portfolio_id": str(portfolio_id),
                "forwards_count": len(results),
            },
        )
        return results

    # -- Queries -----------------------------------------------------------

    async def get_forward(
        self,
        forward_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> FXForwardContract | None:
        record = await self._forward_repo.get_by_id(forward_id, session=session)
        if record is None:
            return None
        return self._to_contract(record)

    async def get_open_forwards(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXForwardContract]:
        records = await self._forward_repo.get_open_by_portfolio(
            portfolio_id,
            session=session,
        )
        return [self._to_contract(r) for r in records]

    async def get_forwards(
        self,
        portfolio_id: UUID,
        *,
        status: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[FXForwardContract]:
        records = await self._forward_repo.get_by_portfolio(
            portfolio_id,
            status=status,
            session=session,
        )
        return [self._to_contract(r) for r in records]

    async def get_summary(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> FXHedgingSummary:
        forwards = await self._forward_repo.get_open_by_portfolio(
            portfolio_id,
            session=session,
        )
        today = date.today()
        total_notional = ZERO
        total_mtm = ZERO
        currency_breakdown: dict[str, Decimal] = {}
        expiring_5d = 0

        for fwd in forwards:
            total_notional += fwd.notional
            total_mtm += fwd.mtm_value or ZERO
            pair = f"{fwd.base_currency}/{fwd.quote_currency}"
            currency_breakdown[pair] = currency_breakdown.get(pair, ZERO) + fwd.notional
            if (fwd.maturity_date - today).days <= 5:
                expiring_5d += 1

        return FXHedgingSummary(
            portfolio_id=portfolio_id,
            open_forwards=len(forwards),
            total_notional=total_notional,
            total_mtm=total_mtm,
            currency_breakdown=currency_breakdown,
            expiring_within_5d=expiring_5d,
            calculated_at=datetime.now(UTC),
        )

    # -- Hedge recommendations ---------------------------------------------

    async def get_hedge_recommendations(
        self,
        portfolio_id: UUID,
        currency_exposures: dict[str, Decimal],
        *,
        hedge_ratio: Decimal = ONE,
        tenor_days: int = 30,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[HedgeRecommendationResponse]:
        """Generate hedge recommendations from currency exposures."""
        spots: dict[str, Decimal] = {}
        foreign_rates: dict[str, Decimal] = {}

        for ccy in currency_exposures:
            if ccy == self._base_currency:
                continue
            spot = self._get_spot(self._base_currency, ccy)
            if spot is not None:
                spots[ccy] = spot
            rate_record = await self._rate_repo.get_by_currency(ccy, session=session)
            foreign_rates[ccy] = rate_record.rate if rate_record else ZERO

        domestic_rate = await self._get_domestic_rate(session=session)

        recs = recommend_hedges(
            currency_exposures=currency_exposures,
            base_currency=self._base_currency,
            spots=spots,
            domestic_rate=domestic_rate,
            foreign_rates=foreign_rates,
            hedge_ratio=hedge_ratio,
            tenor_days=tenor_days,
        )

        await self._publish_event(
            AuditEventType.FX_HEDGE_RECOMMENDED,
            fund_slug,
            {
                "portfolio_id": str(portfolio_id),
                "recommendations_count": len(recs),
            },
        )

        return [
            HedgeRecommendationResponse(
                currency_pair=r.currency_pair,
                base_currency=r.base_currency,
                quote_currency=r.quote_currency,
                notional=r.notional,
                direction=r.direction,
                hedge_ratio=r.hedge_ratio,
                tenor_days=r.tenor_days,
                estimated_forward=r.estimated_forward,
                estimated_cost_bps=r.estimated_cost_bps,
            )
            for r in recs
        ]

    # -- Roll recommendations ----------------------------------------------

    async def get_roll_recommendations(
        self,
        portfolio_id: UUID,
        *,
        days_ahead: int = 5,
        new_tenor_days: int = 30,
        session: AsyncSession | None = None,
    ) -> list[RollRecommendation]:
        """Identify expiring forwards and estimate roll costs."""
        forwards = await self._forward_repo.get_open_by_portfolio(
            portfolio_id,
            session=session,
        )
        today = date.today()
        maturities = [(fwd.id, fwd.maturity_date) for fwd in forwards]
        expiring = identify_expiring_forwards(maturities, today, days_ahead)

        domestic_rate = await self._get_domestic_rate(session=session)
        recs: list[RollRecommendation] = []

        for fwd_id, mat_date, days_remaining in expiring:
            fwd = next(f for f in forwards if f.id == fwd_id)
            spot = self._get_spot(fwd.base_currency, fwd.quote_currency)
            if spot is None:
                continue
            foreign_rate = await self._get_rate_for_currency(
                fwd.base_currency,
                session=session,
            )
            cost = calculate_roll_cost(
                contract_rate=fwd.contract_rate,
                contract_notional=fwd.notional,
                direction=fwd.direction,
                current_spot=spot,
                domestic_rate=domestic_rate,
                foreign_rate=foreign_rate,
                remaining_days=max(days_remaining, 1),
                new_tenor_days=new_tenor_days,
            )
            recs.append(
                RollRecommendation(
                    forward_id=UUID(fwd_id),
                    maturity_date=mat_date,
                    days_remaining=days_remaining,
                    current_mtm=cost.close_mtm,
                    suggested_new_tenor_days=new_tenor_days,
                    estimated_roll_cost_bps=cost.cost_bps,
                )
            )
        return recs

    # -- Interest rates ----------------------------------------------------

    async def set_interest_rate(
        self,
        currency: str,
        rate: Decimal,
        *,
        tenor_days: int = 30,
        source: str = "manual",
        session: AsyncSession | None = None,
    ) -> None:
        """Set or update the interest rate for a currency."""
        record = FXInterestRateRecord(
            currency=currency,
            rate=rate,
            tenor_days=tenor_days,
            source=source,
            updated_at=datetime.now(UTC),
        )
        await self._rate_repo.upsert(record, session=session)
        logger.info("fx_interest_rate_set", currency=currency, rate=str(rate))

    async def get_interest_rates(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXInterestRateRecord]:
        return await self._rate_repo.list_all(session=session)

    # -- Internal helpers --------------------------------------------------

    def _get_spot(self, base: str, quote: str) -> Decimal | None:
        """Get spot rate from in-memory FX converter."""
        if self._fx is None:
            return None
        return self._fx.get_rate(base, quote)

    async def _get_domestic_rate(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> Decimal:
        """Get base currency interest rate."""
        record = await self._rate_repo.get_by_currency(
            self._base_currency,
            session=session,
        )
        return record.rate if record else ZERO

    async def _get_rate_for_currency(
        self,
        currency: str,
        *,
        session: AsyncSession | None = None,
    ) -> Decimal:
        record = await self._rate_repo.get_by_currency(currency, session=session)
        return record.rate if record else ZERO

    @staticmethod
    def _to_contract(record: FXForwardRecord) -> FXForwardContract:
        return FXForwardContract(
            id=UUID(record.id),
            portfolio_id=UUID(record.portfolio_id),
            base_currency=record.base_currency,
            quote_currency=record.quote_currency,
            direction=record.direction,  # type: ignore[arg-type]
            notional=record.notional,
            contract_rate=record.contract_rate,
            spot_at_inception=record.spot_at_inception,
            trade_date=record.trade_date,
            maturity_date=record.maturity_date,
            status=record.status,  # type: ignore[arg-type]
            counterparty=record.counterparty,
            roll_from_id=UUID(record.roll_from_id) if record.roll_from_id else None,
            mtm_value=record.mtm_value,
            mtm_timestamp=record.mtm_timestamp,
            created_at=record.created_at,
        )

    async def _publish_event(
        self,
        event_type: AuditEventType,
        fund_slug: str | None,
        data: dict[str, object],
    ) -> None:
        if self._event_bus is None or not fund_slug:
            return
        event = BaseEvent(
            event_type=event_type,
            data=data,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "fx-hedging.events"),
            event,
        )
