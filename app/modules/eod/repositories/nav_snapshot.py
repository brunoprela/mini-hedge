"""NAV snapshot persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models.nav_snapshot import NAVSnapshotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NAVSnapshotRepository(BaseRepository):
    """Data access for NAV snapshots."""

    async def get_history(
        self,
        portfolio_ids: list[str],
        *,
        since: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[NAVSnapshotRecord]:
        """Return NAV snapshots for given portfolios ordered by date ascending."""
        async with self._session(session) as s:
            stmt = (
                select(NAVSnapshotRecord)
                .where(NAVSnapshotRecord.portfolio_id.in_(portfolio_ids))
            )
            if since is not None:
                stmt = stmt.where(NAVSnapshotRecord.business_date >= since)
            stmt = stmt.order_by(NAVSnapshotRecord.business_date.asc())
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self,
        *,
        portfolio_id: str,
        business_date: date,
        gross_market_value: Any,
        net_market_value: Any,
        cash_balance: Any,
        accrued_fees: Any,
        nav: Any,
        nav_per_share: Any,
        shares_outstanding: Any,
        currency: str,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(NAVSnapshotRecord).values(
                portfolio_id=portfolio_id,
                business_date=business_date,
                gross_market_value=gross_market_value,
                net_market_value=net_market_value,
                cash_balance=cash_balance,
                accrued_fees=accrued_fees,
                nav=nav,
                nav_per_share=nav_per_share,
                shares_outstanding=shares_outstanding,
                currency=currency,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=NAVSnapshotRecord.__table__.primary_key,  # type: ignore[arg-type]
                set_={
                    "nav": stmt.excluded.nav,
                    "net_market_value": stmt.excluded.net_market_value,
                    "gross_market_value": stmt.excluded.gross_market_value,
                    "cash_balance": stmt.excluded.cash_balance,
                    "accrued_fees": stmt.excluded.accrued_fees,
                    "nav_per_share": stmt.excluded.nav_per_share,
                    "shares_outstanding": stmt.excluded.shares_outstanding,
                },
            )
            await s.execute(stmt)
            await s.commit()
