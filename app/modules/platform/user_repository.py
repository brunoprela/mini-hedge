"""Data access for user records."""

from sqlalchemy import select, update

from app.modules.platform.models import UserRecord
from app.shared.database import TenantSessionFactory


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

    async def get_all(self) -> list[UserRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(UserRecord))
            return list(result.scalars().all())

    async def update(self, user_id: str, **fields: object) -> UserRecord | None:
        async with self._session_factory() as session:
            if fields:
                await session.execute(
                    update(UserRecord).where(UserRecord.id == user_id).values(**fields)
                )
                await session.commit()
            result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
            return result.scalar_one_or_none()
