"""Data access for fund membership records."""

from sqlalchemy import select

from app.modules.platform.models import FundMembershipRecord, FundRecord, FundStatus
from app.shared.database import TenantSessionFactory


class FundMembershipRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_user_and_fund(self, user_id: str, fund_id: str) -> FundMembershipRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundMembershipRecord).where(
                    FundMembershipRecord.user_id == user_id,
                    FundMembershipRecord.fund_id == fund_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_by_user(self, user_id: str) -> list[FundMembershipRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundMembershipRecord).where(FundMembershipRecord.user_id == user_id)
            )
            return list(result.scalars().all())

    async def get_funds_for_user(
        self, user_id: str
    ) -> list[tuple[FundRecord, FundMembershipRecord]]:
        """Return all (fund, membership) pairs for a user."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundRecord, FundMembershipRecord)
                .join(
                    FundMembershipRecord,
                    FundRecord.id == FundMembershipRecord.fund_id,
                )
                .where(
                    FundMembershipRecord.user_id == user_id,
                    FundRecord.status == FundStatus.ACTIVE,
                )
            )
            return list(result.tuples().all())

    async def insert(self, record: FundMembershipRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
