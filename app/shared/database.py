"""Async SQLAlchemy engine and session factory with tenant isolation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.shared.request_context import get_request_context


class TenantSessionFactory:
    """Wraps async_sessionmaker to set app.current_fund_id per transaction.

    Reads fund_id from the current RequestContext via contextvars.
    When no context exists (system/MTM/migrations), sets 'BYPASS' to skip RLS.

    SET LOCAL scopes the variable to the current transaction — it auto-clears
    when the session ends, so pooled connections are never contaminated.
    """

    def __init__(self, inner: async_sessionmaker[AsyncSession]) -> None:
        self._inner = inner

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        async with self._inner() as session:
            fund_id = self._resolve_fund_id()
            if fund_id is not None:
                # SET LOCAL doesn't support bind parameters in PostgreSQL.
                # Validate as UUID to prevent SQL injection, then interpolate.
                safe_id = str(UUID(fund_id))
                await session.execute(
                    text(f"SET LOCAL app.current_fund_id = '{safe_id}'"),
                )
            else:
                await session.execute(
                    text("SET LOCAL app.current_fund_id = 'BYPASS'"),
                )
            yield session

    @staticmethod
    def _resolve_fund_id() -> str | None:
        """Read fund_id from the current request context, or None for system.

        Returns None (→ BYPASS) only when no request context exists at all,
        which is correct for system processes like MTM and migrations.
        If a request context exists but fund_id is missing, that's a bug
        in the auth layer — raise rather than silently bypassing RLS.
        """
        try:
            ctx = get_request_context()
        except RuntimeError:
            return None  # No request context → system/MTM → BYPASS
        if ctx.fund_id is None:
            raise RuntimeError(
                f"Request context exists (actor={ctx.actor_id}) but fund_id is None. "
                "This indicates a bug in the auth layer — RLS cannot be applied."
            )
        return ctx.fund_id


def build_engine(
    database_url: str | None = None,
) -> tuple[AsyncEngine, TenantSessionFactory]:
    settings = get_settings()
    url = database_url or settings.database_url
    engine = create_async_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    raw_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, TenantSessionFactory(raw_factory)
