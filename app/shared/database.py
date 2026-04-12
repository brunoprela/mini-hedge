"""Async SQLAlchemy engine and session factory with per-fund schema isolation.

Each fund's position data lives in its own PostgreSQL schema (``fund_{slug}``).
The ``TenantSessionFactory`` transparently rewrites queries against the
``positions`` schema to the active fund's schema using SQLAlchemy's
``schema_translate_map``.

Shared data (platform, security_master, market_data) uses fixed schemas
and is unaffected by the translation.

Session lifecycle
-----------------
HTTP requests receive a session via the ``get_db`` FastAPI dependency, which
routes pass explicitly to services and repositories. This gives one pool
checkout per request, snapshot isolation, and full testability.

Background tasks (Kafka handlers) don't go through FastAPI routes, so
repositories still support creating their own session from the factory
when no session is provided.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import ClassVar

from fastapi import Request  # noqa: TC002 — must be runtime for FastAPI dependency injection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from app.config import get_settings
from app.shared.errors import CustomerContextMissing, FundContextMissing
from app.shared.fund_schema import fund_schema_name

# Schema name used in positions ORM models (__table_args__ schema key).
# This is the key in schema_translate_map that gets rewritten per-fund.
_POSITIONS_SCHEMA = "positions"


class EngineRouter:
    """Routes database connections per customer.

    In the current single-database deployment, all customers share one engine.
    Future: register per-customer engines for physical tenant isolation.
    """

    def __init__(self, default_engine: AsyncEngine) -> None:
        self._default = default_engine
        self._customer_engines: dict[str, AsyncEngine] = {}

    def register(self, customer_id: str, engine: AsyncEngine) -> None:
        """Register a dedicated engine for a customer."""
        self._customer_engines[customer_id] = engine

    def resolve(self, customer_id: str | None) -> AsyncEngine:
        """Return the engine for a customer, falling back to the default."""
        if customer_id and customer_id in self._customer_engines:
            return self._customer_engines[customer_id]
        return self._default

    @property
    def default_engine(self) -> AsyncEngine:
        return self._default

    @property
    def customer_count(self) -> int:
        """Number of customers with dedicated engines."""
        return len(self._customer_engines)

    async def dispose_all(self) -> None:
        """Dispose all engines (shutdown)."""
        await self._default.dispose()
        for engine in self._customer_engines.values():
            await engine.dispose()


class TenantSessionFactory:
    """Creates sessions with per-fund schema isolation and read/write routing.

    Schema resolution is driven by two ``ContextVar``s:
    - ``_customer_id_var`` — selects the customer database via EngineRouter
    - ``_fund_slug_var`` — selects the fund schema within that database

    Both HTTP middleware and Kafka handlers use the same mechanism::

        async with sf.customer_scope("cust-uuid"):
            async with sf.fund_scope("alpha"):
                async with sf() as session:
                    ...  # session targets fund_alpha schema

    When no fund scope is active, sessions target shared schemas only
    (platform, security_master, market_data).

    Read/write routing
    ------------------
    If a read engine is configured, ``read_session()`` returns a session
    bound to the read replica for query-heavy paths (dashboards, reports).
    The default ``__call__`` always uses the write engine.
    """

    # Task-local tenant context. ``contextvars`` are scoped to the current
    # ``asyncio.Task``, so concurrent consumers for different funds/customers
    # don't interfere with each other.
    _customer_id_var: ClassVar[ContextVar[str | None]] = ContextVar(
        "_customer_id_var", default=None
    )
    _fund_slug_var: ClassVar[ContextVar[str | None]] = ContextVar("_fund_slug_var", default=None)

    def __init__(
        self,
        engine: AsyncEngine,
        read_engine: AsyncEngine | None = None,
        engine_router: EngineRouter | None = None,
    ) -> None:
        self._engine = engine
        self._read_engine = read_engine
        self._engine_router = engine_router or EngineRouter(engine)

    @property
    def engine_router(self) -> EngineRouter:
        return self._engine_router

    def _resolve_engine(self, base_engine: AsyncEngine | None = None) -> AsyncEngine:
        """Resolve the engine for the current customer + fund context.

        Uses the EngineRouter to select the customer's engine, then applies
        fund schema translation on top.
        """
        customer_id = self._customer_id_var.get()
        engine = self._engine_router.resolve(customer_id) if base_engine is None else base_engine
        fund_slug = self._fund_slug_var.get()
        if fund_slug is not None:
            return engine.execution_options(
                schema_translate_map={_POSITIONS_SCHEMA: fund_schema_name(fund_slug)},
            )
        return engine

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        """Write session scoped to the active customer + fund schema."""
        engine = self._resolve_engine()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    @asynccontextmanager
    async def read_session(self) -> AsyncIterator[AsyncSession]:
        """Read-only session routed to the replica (falls back to primary)."""
        base = self._read_engine or self._engine
        engine = self._resolve_engine(base)
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

    @asynccontextmanager
    async def customer_scope(self, customer_id: str) -> AsyncIterator[None]:
        """Set the active customer for the current async task.

        In the current single-database deployment, this is a logical marker
        used for containment checks and audit context. Future: per-customer
        engine routing will use this to select the correct database connection.
        """
        token = self._customer_id_var.set(customer_id)
        try:
            yield
        finally:
            self._customer_id_var.reset(token)

    @classmethod
    def current_customer_id(cls) -> str | None:
        """Return the active customer ID, or None."""
        return cls._customer_id_var.get()

    @classmethod
    def current_fund_slug(cls) -> str | None:
        """Return the active fund slug, or None."""
        return cls._fund_slug_var.get()

    @classmethod
    def require_customer_id(cls) -> str:
        """Return the active customer ID, or raise ``CustomerContextMissing``."""
        cid = cls._customer_id_var.get()
        if cid is None:
            raise CustomerContextMissing()
        return cid

    @classmethod
    def require_fund_slug(cls) -> str:
        """Return the active fund slug, or raise ``FundContextMissing``."""
        slug = cls._fund_slug_var.get()
        if slug is None:
            raise FundContextMissing()
        return slug

    @property
    def has_read_replica(self) -> bool:
        """Whether a separate read engine is configured."""
        return self._read_engine is not None


# ---------------------------------------------------------------------------
# FastAPI session dependency
# ---------------------------------------------------------------------------


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a write session for the entire request.

    Routes should ``Depends(get_db)`` and pass the session explicitly
    to services/repos::

        @router.get("/portfolios/{id}")
        async def get_portfolio(
            id: UUID,
            session: AsyncSession = Depends(get_db),
            service: PortfolioService = Depends(get_service),
        ):
            return await service.get(id, session=session)
    """
    sf: TenantSessionFactory = request.app.state.session_factory
    async with sf() as session:
        yield session


async def get_read_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a read-only session routed to the replica.

    Falls back to the primary if no read replica is configured.
    Use for query-heavy endpoints (dashboards, reports, lists).
    """
    sf: TenantSessionFactory = request.app.state.session_factory
    async with sf.read_session() as session:
        yield session


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
        connect_args={"statement_cache_size": 0},
    )

    # Read replica engine (optional — falls back to primary if not configured)
    read_engine: AsyncEngine | None = None
    if settings.database_read_url:
        read_engine = create_async_engine(
            settings.database_read_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=settings.database_pool_timeout,
            connect_args={"statement_cache_size": 0},
        )

    return engine, TenantSessionFactory(engine, read_engine=read_engine)
