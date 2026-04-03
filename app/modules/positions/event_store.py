"""Append-only event store for position events — the source of truth."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select

from app.modules.positions.interface import (
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeSide,
)
from app.modules.positions.models import PositionEventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.database import TenantSessionFactory


class EventStoreRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_aggregate(
        self, aggregate_id: str, *, session: AsyncSession | None = None
    ) -> list[TradeEvent]:
        async def _query(s: AsyncSession) -> list[TradeEvent]:
            stmt = (
                select(PositionEventRecord)
                .where(PositionEventRecord.aggregate_id == aggregate_id)
                .order_by(PositionEventRecord.sequence_number)
            )
            result = await s.execute(stmt)
            return [self._deserialize(record) for record in result.scalars().all()]

        if session is not None:
            return await _query(session)
        async with self._session_factory() as s:
            return await _query(s)

    async def has_idempotency_key(
        self,
        idempotency_key: str,
        *,
        session: AsyncSession,
    ) -> bool:
        """Check if an event with the given idempotency key already exists."""
        stmt = select(func.count(PositionEventRecord.id)).where(
            PositionEventRecord.metadata_["idempotency_key"].astext == idempotency_key,
        )
        result = await session.execute(stmt)
        return result.scalar_one() > 0

    async def append(
        self,
        aggregate_id: str,
        event_type: str,
        event_data: dict,
        *,
        session: AsyncSession | None = None,
        metadata: dict | None = None,
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
                event_version=1,
                event_data=event_data,
                metadata_=metadata or {},
            )
            s.add(event)

        if session is not None:
            await _append(session)
        else:
            async with self._session_factory() as s:
                await _append(s)
                await s.commit()

    @staticmethod
    def _deserialize(record: PositionEventRecord) -> TradeEvent:
        """Convert a DB record into a typed domain event."""
        data = record.event_data
        return TradeEvent(
            event_type=PositionEventType(record.event_type),
            timestamp=record.created_at,
            data=TradeEventData(
                portfolio_id=UUID(data["portfolio_id"]),
                instrument_id=data["instrument_id"],
                side=TradeSide(data["side"]),
                quantity=Decimal(data["quantity"]),
                price=Decimal(data["price"]),
                trade_id=UUID(data["trade_id"]),
                currency=data["currency"],
            ),
        )

    @staticmethod
    def serialize(event: TradeEvent) -> dict:
        """Convert a typed domain event into a JSONB-safe dict for storage."""
        return {
            "portfolio_id": str(event.data.portfolio_id),
            "instrument_id": event.data.instrument_id,
            "side": event.data.side.value,
            "quantity": str(event.data.quantity),
            "price": str(event.data.price),
            "trade_id": str(event.data.trade_id),
            "currency": event.data.currency,
        }
