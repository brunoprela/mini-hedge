"""Position keeping query service — reads from the position read model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.positions.core.aggregate import PositionAggregate
from app.modules.positions.core.trade_handler import TradeHandler
from app.modules.positions.interfaces import (
    PnLSummary,
    PortfolioSummary,
    Position,
    PositionLot,
    TradeRequest,
)
from app.modules.positions.models.current_position import CurrentPositionRecord
from app.modules.positions.models.lot import LotRecord
from app.modules.positions.repositories import CurrentPositionRepository, LotRepository
from app.shared.auth.request_context import RequestContext

if TYPE_CHECKING:
    from app.modules.positions.core.event_store import EventStoreRepository
    from app.modules.positions.repositories.daily_pnl import DailyPnLRepository

ZERO = Decimal(0)


def _to_lot(record: LotRecord) -> PositionLot:
    return PositionLot(
        id=UUID(record.id),
        portfolio_id=UUID(record.portfolio_id),
        instrument_id=record.instrument_id,
        quantity=record.quantity,
        original_quantity=record.original_quantity,
        price=record.price,
        acquired_at=record.acquired_at,
        trade_id=UUID(record.trade_id),
    )


def _to_position(record: CurrentPositionRecord) -> Position:
    return Position(
        portfolio_id=UUID(record.portfolio_id),
        instrument_id=record.instrument_id,
        quantity=record.quantity,
        avg_cost=record.avg_cost,
        cost_basis=record.cost_basis,
        market_price=record.market_price,
        market_value=record.market_value,
        unrealized_pnl=record.unrealized_pnl,
        currency=record.currency,
        last_updated=record.last_updated,
    )


class PositionService:
    """Implements PositionReader protocol and trade entry."""

    def __init__(
        self,
        *,
        position_repo: CurrentPositionRepository,
        lot_repo: LotRepository | None = None,
        trade_handler: TradeHandler,
        event_store: EventStoreRepository | None = None,
        daily_pnl_repo: DailyPnLRepository | None = None,
    ) -> None:
        self._position_repo = position_repo
        self._lot_repo = lot_repo
        self._trade_handler = trade_handler
        self._event_store = event_store
        self._daily_pnl_repo = daily_pnl_repo

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> Position | None:
        record = await self._position_repo.get_position(
            portfolio_id, instrument_id, session=session
        )
        if record is None:
            return None
        return _to_position(record)

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[Position]:
        records = await self._position_repo.get_by_portfolio(portfolio_id, session=session)
        return [_to_position(r) for r in records]

    async def get_lots(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[PositionLot]:
        if self._lot_repo is None:
            return []
        records = await self._lot_repo.get_lots(portfolio_id, instrument_id, session=session)
        return [_to_lot(r) for r in records]

    async def get_portfolio_summary(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> PortfolioSummary:
        summary = await self._position_repo.get_portfolio_summary(portfolio_id, session=session)
        if summary is None:
            return PortfolioSummary(
                portfolio_id=portfolio_id,
                total_market_value=Decimal(0),
                total_cost_basis=Decimal(0),
                total_realized_pnl=Decimal(0),
                total_unrealized_pnl=Decimal(0),
                position_count=0,
            )
        return PortfolioSummary(
            portfolio_id=portfolio_id,
            total_market_value=Decimal(str(summary["total_market_value"])),
            total_cost_basis=Decimal(str(summary["total_cost_basis"])),
            total_realized_pnl=Decimal(str(summary["total_realized_pnl"])),
            total_unrealized_pnl=Decimal(str(summary["total_unrealized_pnl"])),
            position_count=int(str(summary["position_count"])),
        )

    async def execute_trade(
        self,
        request: TradeRequest,
        request_context: RequestContext,
        *,
        session: AsyncSession | None = None,
    ) -> Position:
        """Process a trade and return the updated position."""
        await self._trade_handler.handle_trade(
            request_context=request_context,
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id.upper(),
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
        )

        # Return updated position (or existing position for idempotent duplicates)
        position = await self.get_position(
            request.portfolio_id, request.instrument_id.upper(), session=session
        )
        if position is None:
            raise LookupError(f"Position read-back failed after trade for {request.instrument_id}")
        return position

    # ------------------------------------------------------------------
    # Point-in-time & P&L queries
    # ------------------------------------------------------------------

    async def get_position_at(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        at: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> Position | None:
        """Replay events up to a point in time to reconstruct position state.

        Returns None if no events exist for the instrument before the given timestamp.
        """
        if self._event_store is None:
            return None
        aggregate_id = f"{portfolio_id}:{instrument_id}"
        events = await self._event_store.get_by_aggregate(
            aggregate_id, before=at, session=session
        )
        if not events:
            return None

        agg = PositionAggregate.from_events(portfolio_id, instrument_id, events)
        return Position(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=agg.quantity,
            avg_cost=agg.avg_cost,
            cost_basis=agg.cost_basis,
            market_price=ZERO,  # no market price in event history
            market_value=ZERO,
            unrealized_pnl=ZERO,
            currency=agg.currency,
            last_updated=events[-1].timestamp,
        )

    async def get_portfolio_pnl(
        self,
        portfolio_id: UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[PnLSummary]:
        """Return daily P&L summaries for a portfolio, aggregated from daily_pnl records."""
        if self._daily_pnl_repo is None:
            return []
        records = await self._daily_pnl_repo.get_by_portfolio(
            str(portfolio_id), from_date=from_date, to_date=to_date, session=session
        )
        # Group by business_date and aggregate
        by_date: dict[date, list] = {}
        for r in records:
            by_date.setdefault(r.business_date, []).append(r)

        summaries = []
        for biz_date, day_records in sorted(by_date.items()):
            total_realized = sum((r.realized_pnl or ZERO) for r in day_records)
            total_unrealized = sum((r.unrealized_pnl or ZERO) for r in day_records)
            currency = day_records[0].currency if day_records else "USD"
            summaries.append(
                PnLSummary(
                    portfolio_id=portfolio_id,
                    date=biz_date,
                    realized_pnl=total_realized,
                    unrealized_pnl=total_unrealized,
                    total_pnl=total_realized + total_unrealized,
                    currency=currency,
                )
            )
        return summaries
