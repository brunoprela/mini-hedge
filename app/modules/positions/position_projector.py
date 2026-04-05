"""Projects aggregate state onto the current_positions and lots read models.

Synchronous — called within the same transaction as event store append.
Designed to be replaceable with an async consumer later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete

from app.modules.positions.models import LotRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.positions.aggregate import PositionAggregate
    from app.modules.positions.event_store import EventStoreRepository
    from app.modules.positions.position_repository import CurrentPositionRepository
    from app.shared.database import TenantSessionFactory


class PositionProjector:
    """Projects aggregate state onto the current_positions and lots read models."""

    def __init__(self, position_repo: CurrentPositionRepository) -> None:
        self._position_repo = position_repo

    async def project(
        self,
        aggregate: PositionAggregate,
        *,
        session: AsyncSession,
        currency: str = "USD",
    ) -> None:
        """Project the aggregate's current state into the read models.

        Must be called within the same transaction as the event store append
        to maintain read-after-write consistency.
        """
        await self._position_repo.upsert(
            portfolio_id=aggregate.portfolio_id,
            instrument_id=aggregate.instrument_id,
            quantity=aggregate.quantity,
            avg_cost=aggregate.avg_cost,
            cost_basis=aggregate.cost_basis,
            realized_pnl=aggregate.realized_pnl,
            currency=currency,
            session=session,
        )
        await self._project_lots(aggregate, session=session)

    async def _project_lots(
        self,
        aggregate: PositionAggregate,
        *,
        session: AsyncSession,
    ) -> None:
        """Replace lots for this position with the aggregate's current lot state.

        Delete-and-reinsert is correct here: lots are small per position,
        and the aggregate is the authoritative source after event replay.
        """
        # Delete existing lots for this position
        await session.execute(
            delete(LotRecord).where(
                LotRecord.portfolio_id == str(aggregate.portfolio_id),
                LotRecord.instrument_id == aggregate.instrument_id,
            )
        )

        # Insert current lots from aggregate
        for lot in aggregate.lots:
            session.add(
                LotRecord(
                    id=str(lot.lot_id),
                    portfolio_id=str(aggregate.portfolio_id),
                    instrument_id=aggregate.instrument_id,
                    quantity=lot.quantity,
                    original_quantity=lot.original_quantity,
                    price=lot.price,
                    acquired_at=lot.acquired_at,
                    trade_id=str(lot.trade_id),
                )
            )

    async def rebuild(
        self,
        aggregate_id: str,
        *,
        event_store: EventStoreRepository,
        session_factory: TenantSessionFactory,
    ) -> None:
        """Rebuild the read model for a single aggregate from the event store.

        Use this for drift correction — replays all events and re-projects.
        """
        from app.modules.positions.aggregate import PositionAggregate

        portfolio_id_str, instrument_id = aggregate_id.split(":")
        portfolio_id = UUID(portfolio_id_str)

        events = await event_store.get_by_aggregate(aggregate_id)
        aggregate = PositionAggregate.from_events(portfolio_id, instrument_id, events)

        async with session_factory() as session:
            await self._position_repo.upsert(
                portfolio_id=aggregate.portfolio_id,
                instrument_id=aggregate.instrument_id,
                quantity=aggregate.quantity,
                avg_cost=aggregate.avg_cost,
                cost_basis=aggregate.cost_basis,
                realized_pnl=aggregate.realized_pnl,
                currency="USD",
                session=session,
            )
            await self._project_lots(aggregate, session=session)
            await session.commit()
