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
from contextvars import ContextVar
from typing import ClassVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from app.config import get_settings
from app.shared.fund_schema import fund_schema_name

# Schema name used in positions ORM models (__table_args__ schema key).
# This is the key in schema_translate_map that gets rewritten per-fund.
_POSITIONS_SCHEMA = "positions"


class TenantSessionFactory:
    """Creates sessions with per-fund schema isolation.

    Schema resolution is driven by a single ``ContextVar`` set via
    ``fund_scope()``.  Both HTTP middleware and Kafka handlers use
    the same mechanism::

        async with sf.fund_scope("alpha"):
            async with sf() as session:
                ...  # session targets fund_alpha schema

    When no fund scope is active, sessions target shared schemas only
    (platform, security_master, market_data).
    """

    # Task-local fund slug. ``contextvars`` are scoped to the current
    # ``asyncio.Task``, so concurrent consumers for different funds
    # don't interfere with each other.
    _fund_slug_var: ClassVar[ContextVar[str | None]] = ContextVar("_fund_slug_var", default=None)

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        """Session scoped to the active fund schema (if any)."""
        fund_slug = self._fund_slug_var.get()
        engine = self._engine
        if fund_slug is not None:
            engine = engine.execution_options(
                schema_translate_map={_POSITIONS_SCHEMA: fund_schema_name(fund_slug)},
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    @asynccontextmanager
    async def fund_scope(self, fund_slug: str) -> AsyncIterator[None]:
        """Set the active fund for the current async task.

        Every ``self()`` call within this block will target
        ``fund_{slug}``::

            async with sf.fund_scope(event.fund_slug):
                await some_service.do_work(portfolio_id)
        """
        token = self._fund_slug_var.set(fund_slug)
        try:
            yield
        finally:
            self._fund_slug_var.reset(token)

    @classmethod
    def current_fund_slug(cls) -> str | None:
        """Return the active fund slug, or None."""
        return cls._fund_slug_var.get()


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
        pool_recycle=1800,
        pool_timeout=settings.database_pool_timeout,
    )
    return engine, TenantSessionFactory(engine)
