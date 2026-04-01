"""Integration tests for security master module."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.modules.security_master.service import SecurityMasterService
from app.shared.errors import NotFoundError


@pytest.mark.integration
class TestSecurityMaster:
    @pytest.mark.asyncio
    async def test_seed_and_query(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = InstrumentRepository(session_factory)
        records = build_seed_records()
        await repo.insert_batch(records)

        service = SecurityMasterService(repo)

        # Query all
        instruments = await service.get_all_active()
        assert len(instruments) == 10

        # Query by ticker
        aapl = await service.get_by_ticker("AAPL")
        assert aapl.name == "Apple Inc."
        assert aapl.sector == "Technology"

        # Search
        results = await service.search("gold")
        assert len(results) == 1
        assert results[0].ticker == "GS"

    @pytest.mark.asyncio
    async def test_not_found(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = InstrumentRepository(session_factory)
        service = SecurityMasterService(repo)

        with pytest.raises(NotFoundError):
            await service.get_by_ticker("DOESNOTEXIST")
