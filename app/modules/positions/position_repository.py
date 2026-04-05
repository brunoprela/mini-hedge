"""Read model data access for current positions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.modules.positions.models import CurrentPositionRecord, LotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CurrentPositionRepository(BaseRepository):
    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> CurrentPositionRecord | None:
        async with self._session(session) as session:
            stmt = select(CurrentPositionRecord).where(
                CurrentPositionRecord.portfolio_id == str(portfolio_id),
                CurrentPositionRecord.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[CurrentPositionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(CurrentPositionRecord)
                .where(CurrentPositionRecord.portfolio_id == str(portfolio_id))
                .order_by(CurrentPositionRecord.instrument_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        quantity: Decimal,
        avg_cost: Decimal,
        cost_basis: Decimal,
        realized_pnl: Decimal,
        currency: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async def _upsert(s: AsyncSession) -> None:
            now = datetime.now(UTC)
            ins = pg_insert(CurrentPositionRecord).values(
                portfolio_id=str(portfolio_id),
                instrument_id=instrument_id,
                quantity=quantity,
                avg_cost=avg_cost,
                cost_basis=cost_basis,
                realized_pnl=realized_pnl,
                market_price=Decimal(0),
                market_value=Decimal(0),
                unrealized_pnl=Decimal(0),
                currency=currency,
                last_updated=now,
            )
            # On conflict: update trade-derived fields, preserve MTM fields
            stmt = ins.on_conflict_do_update(
                index_elements=["portfolio_id", "instrument_id"],
                set_={
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "cost_basis": cost_basis,
                    "realized_pnl": realized_pnl,
                    "last_updated": now,
                },
            )
            await s.execute(stmt)

        async with self._session(session) as s:
            await _upsert(s)
            if session is None:
                await s.commit()

    async def update_market_value(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        market_price: Decimal,
        market_value: Decimal,
        unrealized_pnl: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            stmt = select(CurrentPositionRecord).where(
                CurrentPositionRecord.portfolio_id == str(portfolio_id),
                CurrentPositionRecord.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()
            if position is not None:
                position.market_price = market_price
                position.market_value = market_value
                position.unrealized_pnl = unrealized_pnl
                position.last_updated = datetime.now(UTC)
                await session.commit()

    async def get_by_instrument(
        self, instrument_id: str, *, session: AsyncSession | None = None
    ) -> list[CurrentPositionRecord]:
        async with self._session(session) as session:
            stmt = select(CurrentPositionRecord).where(
                CurrentPositionRecord.instrument_id == instrument_id
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_portfolio_summary(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, object] | None:
        """Aggregate market value, cost basis, realized and unrealized P&L for a portfolio."""
        async with self._session(session) as session:
            stmt = select(
                func.coalesce(func.sum(CurrentPositionRecord.market_value), Decimal(0)),
                func.coalesce(func.sum(CurrentPositionRecord.cost_basis), Decimal(0)),
                func.coalesce(func.sum(CurrentPositionRecord.realized_pnl), Decimal(0)),
                func.coalesce(func.sum(CurrentPositionRecord.unrealized_pnl), Decimal(0)),
                func.count(),
            ).where(CurrentPositionRecord.portfolio_id == str(portfolio_id))
            result = await session.execute(stmt)
            row = result.one()
            return {
                "total_market_value": row[0],
                "total_cost_basis": row[1],
                "total_realized_pnl": row[2],
                "total_unrealized_pnl": row[3],
                "position_count": row[4],
            }

    async def get_lots(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[LotRecord]:
        async with self._session(session) as session:
            stmt = (
                select(LotRecord)
                .where(
                    LotRecord.portfolio_id == str(portfolio_id),
                    LotRecord.instrument_id == instrument_id,
                )
                .order_by(LotRecord.acquired_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
