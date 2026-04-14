"""Investor repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.platform.models.investor import InvestorRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InvestorRepository(BaseRepository):
    """CRUD for platform.investors."""

    async def get_all_active(self, *, session: AsyncSession | None = None) -> list[InvestorRecord]:
        async with self._session(session) as session:
            stmt = (
                select(InvestorRecord)
                .where(InvestorRecord.is_active.is_(True))
                .order_by(InvestorRecord.name)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            stmt = select(InvestorRecord).where(InvestorRecord.id == investor_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(self, record: InvestorRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()

    async def update(
        self,
        investor_id: str,
        *,
        name: str | None = None,
        entity_type: str | None = None,
        tax_jurisdiction: str | None = None,
        contact_email: str | None = None,
        keycloak_sub: str | None = None,
        is_active: bool | None = None,
        session: AsyncSession | None = None,
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            record = (
                await session.execute(
                    select(InvestorRecord).where(InvestorRecord.id == investor_id)
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            if name is not None:
                record.name = name
            if entity_type is not None:
                record.entity_type = entity_type
            if tax_jurisdiction is not None:
                record.tax_jurisdiction = tax_jurisdiction
            if contact_email is not None:
                record.contact_email = contact_email
            if keycloak_sub is not None:
                record.keycloak_sub = keycloak_sub
            if is_active is not None:
                record.is_active = is_active
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_email(
        self, email: str, *, session: AsyncSession | None = None
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            stmt = select(InvestorRecord).where(
                InvestorRecord.contact_email == email,
                InvestorRecord.is_active.is_(True),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_keycloak_sub(
        self, keycloak_sub: str, *, session: AsyncSession | None = None
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            stmt = select(InvestorRecord).where(InvestorRecord.keycloak_sub == keycloak_sub)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert_batch(
        self, records: list[InvestorRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add_all(records)
            await session.flush()
            await session.commit()
