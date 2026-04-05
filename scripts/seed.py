"""Standalone seed script for local development.

Seeds the database with funds, users, operators, API keys, and instruments
using the platform's Python API.  Run via:

    uv run python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `app` is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from app.modules.platform.api_key_repository import APIKeyRepository
from app.modules.platform.fund_repository import FundRepository
from app.modules.platform.operator_repository import OperatorRepository
from app.modules.platform.seed import (
    DEV_API_KEY,
    build_seed_api_keys,
    build_seed_funds,
    build_seed_operators,
    build_seed_users,
)
from app.modules.platform.user_repository import UserRepository
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.shared.database import TenantSessionFactory, build_engine

logger = structlog.get_logger()


async def seed_platform(session_factory: TenantSessionFactory) -> None:
    """Seed funds, users, operators, and API keys."""
    fund_repo = FundRepository(session_factory)
    user_repo = UserRepository(session_factory)
    operator_repo = OperatorRepository(session_factory)
    api_key_repo = APIKeyRepository(session_factory)

    existing_funds = await fund_repo.get_all_active()
    if not existing_funds:
        funds = build_seed_funds()
        for fund in funds:
            await fund_repo.insert(fund)
        logger.info("funds_seeded", count=len(funds))

    existing_users = await user_repo.get_all_active()
    if not existing_users:
        users = build_seed_users()
        for user in users:
            await user_repo.insert(user)
        api_keys = build_seed_api_keys()
        for api_key in api_keys:
            await api_key_repo.insert(api_key)
        logger.info("auth_seeded", users=len(users), api_key=DEV_API_KEY)

    existing_operators = await operator_repo.get_all_active()
    if not existing_operators:
        operators = build_seed_operators()
        for op in operators:
            await operator_repo.insert(op)
        logger.info("operators_seeded", count=len(operators))


async def seed_instruments(session_factory: TenantSessionFactory) -> None:
    """Seed instrument reference data."""
    instrument_repo = InstrumentRepository(session_factory)
    existing = await instrument_repo.get_all_active()
    if existing:
        logger.info("instruments_already_seeded", count=len(existing))
        return

    instruments, extensions = build_seed_records()
    await instrument_repo.insert_batch(instruments, extensions)
    logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


async def main() -> None:
    engine, session_factory = build_engine()

    try:
        await seed_platform(session_factory)
        await seed_instruments(session_factory)
        logger.info("seed_complete")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
