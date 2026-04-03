"""Data access for the positions schema — event store + read model."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.modules.positions.models import CurrentPositionRecord, PositionEventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.database import TenantSessionFactory


class StoredEvent(TypedDict):
    event_type: str
    timestamp: str
    data: dict[str, Any]


class EventStoreRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_aggregate(
        self, aggregate_id: str, *, session: AsyncSession | None = None
    ) -> list[StoredEvent]:
        async def _query(s: AsyncSession) -> list[StoredEvent]:
            stmt = (
                select(PositionEventRecord)
                .where(PositionEventRecord.aggregate_id == aggregate_id)
                .order_by(PositionEventRecord.sequence_number)
            )
            result = await s.execute(stmt)
            return [
                {
                    "event_type": e.event_type,
                    "timestamp": e.created_at.isoformat(),
                    "data": e.event_data,
                }
                for e in result.scalars().all()
            ]

        if session is not None:
            return await _query(session)
        async with self._session_factory() as s:
            return await _query(s)

    async def append(
        self,
        aggregate_id: str,
        event_type: str,
        event_data: dict,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Append an event with an atomically generated sequence number.

        The sequence number is derived from MAX() + 1 within the same
        transaction. The UNIQUE(aggregate_id, sequence_number) constraint
        ensures correctness under concurrency — a conflicting insert will
        raise IntegrityError, causing the transaction to roll back.
        If an external session is provided, the caller is responsible for
        committing the transaction.
        """

        async def _append(s: AsyncSession) -> None:
            stmt = select(func.coalesce(func.max(PositionEventRecord.sequence_number), 0)).where(
                PositionEventRecord.aggregate_id == aggregate_id
            )
            result = await s.execute(stmt)
            next_seq = result.scalar_one() + 1

            event = PositionEventRecord(
                aggregate_id=aggregate_id,
                sequence_number=next_seq,
                event_type=event_type,
                event_data=event_data,
            )
            s.add(event)

        if session is not None:
            await _append(session)
        else:
            async with self._session_factory() as s:
                await _append(s)
                await s.commit()


class CurrentPositionRepository:
    def __init__(
        self,
        session_factory: TenantSessionFactory,
        *,
        fund_slug: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._fund_slug = fund_slug

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        """Get a session — uses explicit fund_slug if set, else request context."""
        if self._fund_slug is not None:
            async with self._session_factory.for_fund(self._fund_slug) as session:
                yield session
        else:
            async with self._session_factory() as session:
                yield session

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> CurrentPositionRecord | None:
        async with self._session() as session:
            stmt = select(CurrentPositionRecord).where(
                CurrentPositionRecord.portfolio_id == str(portfolio_id),
                CurrentPositionRecord.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
    ) -> list[CurrentPositionRecord]:
        async with self._session() as session:
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

        if session is not None:
            await _upsert(session)
        else:
            async with self._session() as s:
                await _upsert(s)
                await s.commit()

    async def update_market_value(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        market_price: Decimal,
        market_value: Decimal,
        unrealized_pnl: Decimal,
    ) -> None:
        async with self._session() as session:
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

    async def get_by_instrument(self, instrument_id: str) -> list[CurrentPositionRecord]:
        async with self._session() as session:
            stmt = select(CurrentPositionRecord).where(
                CurrentPositionRecord.instrument_id == instrument_id
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
