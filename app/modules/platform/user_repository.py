"""Data access for user records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from app.modules.platform.models import UserRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.interface import UpdateUserRequest


class UserRepository(BaseRepository):
    async def get_by_id(
        self, user_id: str, *, session: AsyncSession | None = None
    ) -> UserRecord | None:
        async with self._session(session) as session:
            result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
            return result.scalar_one_or_none()

    async def get_by_email(
        self, email: str, *, session: AsyncSession | None = None
    ) -> UserRecord | None:
        async with self._session(session) as session:
            result = await session.execute(select(UserRecord).where(UserRecord.email == email))
            return result.scalar_one_or_none()

    async def insert(self, record: UserRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_by_keycloak_sub(
        self, keycloak_sub: str, *, session: AsyncSession | None = None
    ) -> UserRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(UserRecord).where(UserRecord.keycloak_sub == keycloak_sub)
            )
            return result.scalar_one_or_none()

    async def upsert_from_keycloak(
        self, *, keycloak_sub: str, email: str, name: str, session: AsyncSession | None = None
    ) -> UserRecord:
        """JIT sync: create or update a user from Keycloak claims."""
        async with self._session(session) as session:
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

    async def get_all_active(self, *, session: AsyncSession | None = None) -> list[UserRecord]:
        async with self._session(session) as session:
            result = await session.execute(select(UserRecord).where(UserRecord.is_active.is_(True)))
            return list(result.scalars().all())

    async def get_all(self, *, session: AsyncSession | None = None) -> list[UserRecord]:
        async with self._session(session) as session:
            result = await session.execute(select(UserRecord))
            return list(result.scalars().all())

    async def get_all_paginated(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> tuple[list[UserRecord], int]:
        async with self._session(session) as session:
            total = (await session.execute(select(func.count(UserRecord.id)))).scalar_one()
            result = await session.execute(
                select(UserRecord).order_by(UserRecord.name).offset(offset).limit(limit)
            )
            return list(result.scalars().all()), total

    async def update(
        self,
        user_id: str,
        updates: UpdateUserRequest,
        *,
        session: AsyncSession | None = None,
    ) -> UserRecord | None:
        async with self._session(session) as session:
            values = updates.model_dump(exclude_none=True)
            if values:
                await session.execute(
                    update(UserRecord).where(UserRecord.id == user_id).values(**values)
                )
                await session.commit()
            result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
            return result.scalar_one_or_none()
