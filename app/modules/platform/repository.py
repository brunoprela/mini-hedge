"""Data access for platform schema — funds, portfolios, users, API keys."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

from app.modules.platform.models import (
    APIKeyRecord,
    FundMembershipRecord,
    FundRecord,
    FundStatus,
    PortfolioRecord,
    UserRecord,
)
from app.shared.database import TenantSessionFactory


class FundRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, fund_id: str) -> FundRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.id == fund_id))
            return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> FundRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.slug == slug))
            return result.scalar_one_or_none()

    async def get_all_active(self) -> list[FundRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundRecord).where(FundRecord.status == FundStatus.ACTIVE)
            )
            return list(result.scalars().all())

    async def insert(self, record: FundRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()


class PortfolioRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_fund(self, fund_id: str) -> list[PortfolioRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PortfolioRecord).where(
                    PortfolioRecord.fund_id == fund_id,
                    PortfolioRecord.is_active.is_(True),
                )
            )
            return list(result.scalars().all())

    async def get_by_id(self, portfolio_id: UUID) -> PortfolioRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PortfolioRecord).where(PortfolioRecord.id == str(portfolio_id))
            )
            return result.scalar_one_or_none()

    async def insert(self, record: PortfolioRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

    async def insert_batch(self, records: list[PortfolioRecord]) -> None:
        async with self._session_factory() as session:
            session.add_all(records)
            await session.commit()


class UserRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
            return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(UserRecord).where(UserRecord.email == email))
            return result.scalar_one_or_none()

    async def insert(self, record: UserRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

    async def get_by_keycloak_sub(self, keycloak_sub: str) -> UserRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserRecord).where(UserRecord.keycloak_sub == keycloak_sub)
            )
            return result.scalar_one_or_none()

    async def upsert_from_keycloak(self, *, keycloak_sub: str, email: str, name: str) -> UserRecord:
        """JIT sync: create or update a user from Keycloak claims."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserRecord).where(UserRecord.keycloak_sub == keycloak_sub)
            )
            user = result.scalar_one_or_none()

            if user is not None:
                if user.email != email or user.name != name:
                    await session.execute(
                        update(UserRecord)
                        .where(UserRecord.id == user.id)
                        .values(email=email, name=name)
                    )
                    await session.commit()
                    user.email = email
                    user.name = name
                return user

            # Check if a user with this email already exists (seed data)
            result = await session.execute(select(UserRecord).where(UserRecord.email == email))
            user = result.scalar_one_or_none()
            if user is not None:
                await session.execute(
                    update(UserRecord)
                    .where(UserRecord.id == user.id)
                    .values(keycloak_sub=keycloak_sub, name=name)
                )
                await session.commit()
                user.keycloak_sub = keycloak_sub
                user.name = name
                return user

            # Brand new user
            user = UserRecord(
                keycloak_sub=keycloak_sub,
                email=email,
                name=name,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def get_all_active(self) -> list[UserRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(UserRecord).where(UserRecord.is_active.is_(True)))
            return list(result.scalars().all())


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


class APIKeyRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_hash(self, key_hash: str) -> APIKeyRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(APIKeyRecord).where(
                    APIKeyRecord.key_hash == key_hash,
                    APIKeyRecord.is_active.is_(True),
                )
            )
            record = result.scalar_one_or_none()
            if record and record.expires_at and record.expires_at < datetime.now(UTC):
                return None
            return record

    async def insert(self, record: APIKeyRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
