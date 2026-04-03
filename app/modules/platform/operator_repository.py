"""Data access for operator records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from app.modules.platform.models import OperatorRecord

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class OperatorRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, operator_id: str) -> OperatorRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.id == operator_id)
            )
            return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> OperatorRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.email == email)
            )
            return result.scalar_one_or_none()

    async def get_by_keycloak_sub(self, keycloak_sub: str) -> OperatorRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.keycloak_sub == keycloak_sub)
            )
            return result.scalar_one_or_none()

    async def insert(self, record: OperatorRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

    async def upsert_from_keycloak(
        self, *, keycloak_sub: str, email: str, name: str
    ) -> OperatorRecord:
        """JIT sync: create or update an operator from Keycloak claims."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.keycloak_sub == keycloak_sub)
            )
            op = result.scalar_one_or_none()

            if op is not None:
                if op.email != email or op.name != name:
                    await session.execute(
                        update(OperatorRecord)
                        .where(OperatorRecord.id == op.id)
                        .values(email=email, name=name)
                    )
                    await session.commit()
                    op.email = email
                    op.name = name
                return op

            # Check if an operator with this email already exists (seed data)
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.email == email)
            )
            op = result.scalar_one_or_none()
            if op is not None:
                await session.execute(
                    update(OperatorRecord)
                    .where(OperatorRecord.id == op.id)
                    .values(keycloak_sub=keycloak_sub, name=name)
                )
                await session.commit()
                op.keycloak_sub = keycloak_sub
                op.name = name
                return op

            # Brand new operator
            op = OperatorRecord(
                keycloak_sub=keycloak_sub,
                email=email,
                name=name,
                is_active=True,
            )
            session.add(op)
            await session.commit()
            await session.refresh(op)
            return op

    async def get_all_active(self) -> list[OperatorRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.is_active.is_(True))
            )
            return list(result.scalars().all())

    async def get_all(self) -> list[OperatorRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(OperatorRecord))
            return list(result.scalars().all())

    async def get_all_paginated(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[OperatorRecord], int]:
        async with self._session_factory() as session:
            total = (await session.execute(select(func.count(OperatorRecord.id)))).scalar_one()
            result = await session.execute(
                select(OperatorRecord).order_by(OperatorRecord.name).offset(offset).limit(limit)
            )
            return list(result.scalars().all()), total

    async def update(self, operator_id: str, **fields: object) -> OperatorRecord | None:
        async with self._session_factory() as session:
            if fields:
                await session.execute(
                    update(OperatorRecord).where(OperatorRecord.id == operator_id).values(**fields)
                )
                await session.commit()
            result = await session.execute(
                select(OperatorRecord).where(OperatorRecord.id == operator_id)
            )
            return result.scalar_one_or_none()
