"""Async SQLAlchemy engine and session factory with per-fund schema isolation.

Each fund's position data lives in its own PostgreSQL schema (``fund_{slug}``).
The ``TenantSessionFactory`` transparently rewrites queries against the
``positions`` schema to the active fund's schema using SQLAlchemy's
``schema_translate_map``.

Shared data (platform, security_master, market_data) uses fixed schemas
and is unaffected by the translation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from app.config import get_settings
from app.shared.fund_schema import fund_schema_name
from app.shared.request_context import get_request_context

# Schema name used in positions ORM models (__table_args__ schema key).
# This is the key in schema_translate_map that gets rewritten per-fund.
_POSITIONS_SCHEMA = "positions"


class TenantSessionFactory:
    """Creates per-request sessions with schema isolation.

    For authenticated requests the ``positions`` schema is translated to
    ``fund_{slug}`` via ``schema_translate_map``.  For system operations
    (no request context) no translation is applied — callers must use
    :meth:`for_fund` to target a specific fund explicitly.

    ``schema_translate_map`` is set on the engine wrapper, which reuses
    the same connection pool.  There is no per-request overhead beyond
    a lightweight Python dict copy.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        """Session scoped to the current request's fund schema."""
        fund_slug = self._resolve_fund_slug()
        engine = self._engine
        if fund_slug is not None:
            engine = engine.execution_options(
                schema_translate_map={_POSITIONS_SCHEMA: fund_schema_name(fund_slug)},
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    @asynccontextmanager
    async def for_fund(self, fund_slug: str) -> AsyncIterator[AsyncSession]:
        """Session targeting a specific fund schema (for system operations).

        Use this from code that runs outside a request context, such as
        the mark-to-market handler which must iterate over all funds.
        """
        engine = self._engine.execution_options(
            schema_translate_map={_POSITIONS_SCHEMA: fund_schema_name(fund_slug)},
        )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    @asynccontextmanager
    async def unscoped(self) -> AsyncIterator[AsyncSession]:
        """Session with no schema translation (for platform/shared queries)."""
        async with AsyncSession(self._engine, expire_on_commit=False) as session:
            yield session

    @staticmethod
    def _resolve_fund_slug() -> str | None:
        """Read fund_slug from the current request context.

        Returns ``None`` when no request context exists (system operations).
        Unlike the RLS approach, a missing fund_slug on an existing context
        is tolerated — it simply means no schema translation (e.g. the
        ``/me/funds`` endpoint runs before fund selection).
        """
        try:
            ctx = get_request_context()
        except RuntimeError:
            return None  # No request context → system operation
        return ctx.fund_slug if ctx.fund_slug else None


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
    return engine, TenantSessionFactory(engine)
