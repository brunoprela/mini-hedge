"""Standalone seed script — run with: python -m app.seed"""

import asyncio

from app.config import get_settings
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.shared.database import build_engine
from app.shared.logging import setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    _, session_factory = build_engine()

    repo = InstrumentRepository(session_factory)
    existing = await repo.get_all_active()
    if existing:
        print(f"Already have {len(existing)} instruments, skipping seed.")
        return

    records = build_seed_records()
    await repo.insert_batch(records)
    print(f"Seeded {len(records)} instruments.")


if __name__ == "__main__":
    asyncio.run(main())
