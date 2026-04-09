"""P&L snapshot persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models.pnl_snapshot import PnLSnapshotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PnLSnapshotRepository(BaseRepository):
    """Data access for frozen daily P&L."""

    async def upsert(
        self,
        *,
        portfolio_id: str,
        business_date: date,
        total_realized_pnl: Any,
        total_unrealized_pnl: Any,
        total_pnl: Any,
        position_count: int,
        details: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(PnLSnapshotRecord).values(
                portfolio_id=portfolio_id,
                business_date=business_date,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=total_unrealized_pnl,
                total_pnl=total_pnl,
                position_count=position_count,
                details=details,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=PnLSnapshotRecord.__table__.primary_key,  # type: ignore[arg-type]
                set_={
                    "total_realized_pnl": stmt.excluded.total_realized_pnl,
                    "total_unrealized_pnl": stmt.excluded.total_unrealized_pnl,
                    "total_pnl": stmt.excluded.total_pnl,
                    "position_count": stmt.excluded.position_count,
                    "details": stmt.excluded.details,
                },
            )
            await s.execute(stmt)
            await s.commit()
