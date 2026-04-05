"""Base repository with session management.

Provides the ``_session`` helper that lets repo methods work with either:
- An explicitly provided session (from ``Depends(get_db)`` in HTTP routes)
- A self-created session from the factory (for Kafka handlers / background tasks)

Usage::

    class MyRepository(BaseRepository):
        async def get_by_id(self, id: UUID, *, session: AsyncSession | None = None):
            async with self._session(session) as s:
                result = await s.execute(...)
                return result.scalar_one_or_none()
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.database import TenantSessionFactory


class BaseRepository:
    """Base class for repositories with dual-mode session support."""

    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session(self, session: AsyncSession | None = None) -> AsyncIterator[AsyncSession]:
        """Use the provided session, or create one from the factory.

        When a session is provided (HTTP request path), it is yielded as-is
        — no new pool checkout, no commit (caller manages the lifecycle).

        When no session is provided (Kafka handler path), a fresh session
        is created and yielded — the caller is responsible for committing.
        """
        if session is not None:
            yield session
        else:
            async with self._session_factory() as new_session:
                yield new_session
