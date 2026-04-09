"""Security master module wiring — repo, service, dev seeding."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.adapters import ReferenceDataAdapter
    from app.shared.database import TenantSessionFactory

from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records, convert_external_instruments
from app.modules.security_master.service import SecurityMasterService

logger = structlog.get_logger()


def _is_local_env() -> bool:
    return os.environ.get("APP_ENV", "local") == "local"


async def _seed_instruments(
    repo: InstrumentRepository,
    *,
    reference_adapter: ReferenceDataAdapter | None = None,
) -> None:
    existing = await repo.get_all_active()
    if existing:
        return

    if reference_adapter is not None:
        externals = await reference_adapter.get_all_instruments()
        instruments, extensions = convert_external_instruments(externals)
        logger.info("instruments_fetched_from_adapter", count=len(instruments))
    else:
        instruments, extensions = build_seed_records()

    await repo.insert_batch(instruments, extensions)
    logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus=None,
    settings=None,
    reference_adapter: ReferenceDataAdapter | None = None,
    **ctx,
) -> None:
    """Wire security master module: repo, service.  Dev seeding is in seed_dev_data()."""
    instrument_repo = InstrumentRepository(sf)
    app.state.security_master_service = SecurityMasterService(repository=instrument_repo)
    # Dev seeding — only populates data in local environment
    if _is_local_env():
        await _seed_instruments(instrument_repo, reference_adapter=reference_adapter)
