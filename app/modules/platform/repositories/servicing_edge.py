"""Data access for servicing edge records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update

from app.modules.platform.models.servicing_edge import ServicingEdgeRecord, ServicingEdgeStatus
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ServicingEdgeRepository(BaseRepository):
    async def get_active_edge(
        self,
        admin_customer_id: str,
        client_customer_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Return the active servicing edge between two customers, if any."""
        now = datetime.now(UTC)
        async with self._session(session) as session:
            result = await session.execute(
                select(ServicingEdgeRecord).where(
                    and_(
                        ServicingEdgeRecord.admin_customer_id == admin_customer_id,
                        ServicingEdgeRecord.client_customer_id == client_customer_id,
                        ServicingEdgeRecord.status == ServicingEdgeStatus.ACTIVE,
                        ServicingEdgeRecord.effective_from <= now,
                        (
                            ServicingEdgeRecord.effective_until.is_(None)
                            | (ServicingEdgeRecord.effective_until > now)
                        ),
                    )
                )
            )
            return result.scalar_one_or_none()

    async def get_by_id(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Return a servicing edge by its primary key."""
        async with self._session(session) as session:
            result = await session.execute(
                select(ServicingEdgeRecord).where(ServicingEdgeRecord.id == edge_id)
            )
            return result.scalar_one_or_none()

    async def get_client_customers(
        self,
        admin_customer_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ServicingEdgeRecord]:
        """Return all active edges where the given customer is the administrator."""
        now = datetime.now(UTC)
        async with self._session(session) as session:
            result = await session.execute(
                select(ServicingEdgeRecord).where(
                    and_(
                        ServicingEdgeRecord.admin_customer_id == admin_customer_id,
                        ServicingEdgeRecord.status == ServicingEdgeStatus.ACTIVE,
                        ServicingEdgeRecord.effective_from <= now,
                        (
                            ServicingEdgeRecord.effective_until.is_(None)
                            | (ServicingEdgeRecord.effective_until > now)
                        ),
                    )
                )
            )
            return list(result.scalars().all())

    async def get_admin_customers(
        self,
        client_customer_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ServicingEdgeRecord]:
        """Return all active edges where the given customer is the client."""
        now = datetime.now(UTC)
        async with self._session(session) as session:
            result = await session.execute(
                select(ServicingEdgeRecord).where(
                    and_(
                        ServicingEdgeRecord.client_customer_id == client_customer_id,
                        ServicingEdgeRecord.status == ServicingEdgeStatus.ACTIVE,
                        ServicingEdgeRecord.effective_from <= now,
                        (
                            ServicingEdgeRecord.effective_until.is_(None)
                            | (ServicingEdgeRecord.effective_until > now)
                        ),
                    )
                )
            )
            return list(result.scalars().all())

    async def insert(
        self, record: ServicingEdgeRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def update_scoped_roles(
        self,
        edge_id: str,
        scoped_roles: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Update the scoped roles on an edge. Returns the updated record."""
        async with self._session(session) as s:
            await s.execute(
                update(ServicingEdgeRecord)
                .where(ServicingEdgeRecord.id == edge_id)
                .values(scoped_roles=scoped_roles)
            )
            await s.commit()
            return await self.get_by_id(edge_id, session=s)

    async def suspend(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Suspend an active edge."""
        async with self._session(session) as s:
            await s.execute(
                update(ServicingEdgeRecord)
                .where(ServicingEdgeRecord.id == edge_id)
                .values(status=ServicingEdgeStatus.SUSPENDED)
            )
            await s.commit()
            return await self.get_by_id(edge_id, session=s)

    async def terminate(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Terminate an edge by setting status and effective_until."""
        now = datetime.now(UTC)
        async with self._session(session) as s:
            await s.execute(
                update(ServicingEdgeRecord)
                .where(ServicingEdgeRecord.id == edge_id)
                .values(
                    status=ServicingEdgeStatus.TERMINATED,
                    effective_until=now,
                )
            )
            await s.commit()
            return await self.get_by_id(edge_id, session=s)

    async def reactivate(
        self,
        edge_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ServicingEdgeRecord | None:
        """Reactivate a suspended edge."""
        async with self._session(session) as s:
            await s.execute(
                update(ServicingEdgeRecord)
                .where(
                    and_(
                        ServicingEdgeRecord.id == edge_id,
                        ServicingEdgeRecord.status == ServicingEdgeStatus.SUSPENDED,
                    )
                )
                .values(status=ServicingEdgeStatus.ACTIVE, effective_until=None)
            )
            await s.commit()
            return await self.get_by_id(edge_id, session=s)
