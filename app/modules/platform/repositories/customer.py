"""Data access for customer records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.platform.models.customer import CustomerRecord, CustomerStatus
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.interfaces.customer import UpdateCustomerRequest


class CustomerRepository(BaseRepository):
    async def get_by_id(
        self, customer_id: str, *, session: AsyncSession | None = None
    ) -> CustomerRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CustomerRecord).where(CustomerRecord.id == customer_id)
            )
            return result.scalar_one_or_none()

    async def get_by_slug(
        self, slug: str, *, session: AsyncSession | None = None
    ) -> CustomerRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CustomerRecord).where(CustomerRecord.slug == slug)
            )
            return result.scalar_one_or_none()

    async def list_active(
        self, *, session: AsyncSession | None = None
    ) -> list[CustomerRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CustomerRecord).where(CustomerRecord.status == CustomerStatus.ACTIVE)
            )
            return list(result.scalars().all())

    async def list_paginated(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> tuple[list[CustomerRecord], int]:
        async with self._session(session) as session:
            total = (await session.execute(select(func.count(CustomerRecord.id)))).scalar_one()
            result = await session.execute(
                select(CustomerRecord).order_by(CustomerRecord.name).offset(offset).limit(limit)
            )
            return list(result.scalars().all()), total

    async def insert(
        self, record: CustomerRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def update(
        self,
        customer_id: str,
        updates: UpdateCustomerRequest,
        *,
        session: AsyncSession | None = None,
    ) -> CustomerRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CustomerRecord).where(CustomerRecord.id == customer_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None
            for field, value in updates.model_dump(exclude_none=True).items():
                setattr(record, field, value)
            await session.commit()
            await session.refresh(record)
            return record
