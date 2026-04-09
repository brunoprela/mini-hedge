"""VaR result persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.var_result import VaRResultRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class VaRResultRepository(BaseRepository):
    async def save_var_result(
        self,
        result_record: VaRResultRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            session.add(result_record)
            await session.flush()
            await session.commit()

    async def get_latest_var(
        self, portfolio_id: UUID, method: str, *, session: AsyncSession | None = None
    ) -> VaRResultRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(VaRResultRecord)
                .where(
                    VaRResultRecord.portfolio_id == str(portfolio_id),
                    VaRResultRecord.method == method,
                )
                .order_by(VaRResultRecord.calculated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
