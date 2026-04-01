"""Data access for the positions schema — event store + read model."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.positions.models import CurrentPosition, PositionEvent


class EventStoreRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_events(self, aggregate_id: str) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(PositionEvent)
                .where(PositionEvent.aggregate_id == aggregate_id)
                .order_by(PositionEvent.sequence_number)
            )
            result = await session.execute(stmt)
            return [
                {
                    "event_type": e.event_type,
                    "timestamp": e.created_at.isoformat(),
                    "data": e.event_data,
                }
                for e in result.scalars().all()
            ]

    async def get_next_sequence(self, aggregate_id: str) -> int:
        async with self._session_factory() as session:
            stmt = select(func.coalesce(func.max(PositionEvent.sequence_number), 0)).where(
                PositionEvent.aggregate_id == aggregate_id
            )
            result = await session.execute(stmt)
            return result.scalar_one() + 1

    async def append(
        self,
        aggregate_id: str,
        event_type: str,
        event_data: dict,
        sequence_number: int,
    ) -> None:
        async with self._session_factory() as session:
            event = PositionEvent(
                aggregate_id=aggregate_id,
                sequence_number=sequence_number,
                event_type=event_type,
                event_data=event_data,
            )
            session.add(event)
            await session.commit()


class CurrentPositionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> CurrentPosition | None:
        async with self._session_factory() as session:
            stmt = select(CurrentPosition).where(
                CurrentPosition.portfolio_id == str(portfolio_id),
                CurrentPosition.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_portfolio_positions(
        self,
        portfolio_id: UUID,
    ) -> list[CurrentPosition]:
        async with self._session_factory() as session:
            stmt = (
                select(CurrentPosition)
                .where(CurrentPosition.portfolio_id == str(portfolio_id))
                .order_by(CurrentPosition.instrument_id)
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
    ) -> None:
        async with self._session_factory() as session:
            now = datetime.now(UTC)
            stmt = (
                pg_insert(CurrentPosition)
                .values(
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
                .on_conflict_do_update(
                    index_elements=["portfolio_id", "instrument_id"],
                    set_={
                        "quantity": quantity,
                        "avg_cost": avg_cost,
                        "cost_basis": cost_basis,
                        "realized_pnl": realized_pnl,
                        "last_updated": now,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def update_market_value(
        self,
        portfolio_id: str,
        instrument_id: str,
        market_price: Decimal,
        market_value: Decimal,
        unrealized_pnl: Decimal,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(CurrentPosition).where(
                CurrentPosition.portfolio_id == portfolio_id,
                CurrentPosition.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()
            if position is not None:
                position.market_price = market_price
                position.market_value = market_value
                position.unrealized_pnl = unrealized_pnl
                position.last_updated = datetime.now(UTC)
                await session.commit()

    async def get_by_instrument(self, instrument_id: str) -> list[CurrentPosition]:
        async with self._session_factory() as session:
            stmt = select(CurrentPosition).where(CurrentPosition.instrument_id == instrument_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
