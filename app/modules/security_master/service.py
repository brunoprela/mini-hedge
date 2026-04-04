"""Security master business logic — implements the SecurityMasterReader protocol."""

from uuid import UUID

import structlog

from app.modules.security_master.interface import AssetClass, Instrument
from app.modules.security_master.models import InstrumentRecord
from app.modules.security_master.repository import InstrumentRepository
from app.shared.errors import NotFoundError

logger = structlog.get_logger()


def _to_instrument(record: InstrumentRecord) -> Instrument:
    return Instrument(
        id=UUID(record.id),
        name=record.name,
        ticker=record.ticker,
        asset_class=AssetClass(record.asset_class),
        currency=record.currency,
        exchange=record.exchange,
        country=record.country,
        sector=record.sector,
        industry=record.industry,
        annual_drift=record.annual_drift,
        annual_volatility=record.annual_volatility,
        spread_bps=record.spread_bps,
        is_active=record.is_active,
        listed_date=record.listed_date,
    )


class SecurityMasterService:
    """Implements SecurityMasterReader protocol."""

    def __init__(self, repository: InstrumentRepository) -> None:
        self._repo = repository

    async def get_by_id(self, instrument_id: UUID) -> Instrument:
        record = await self._repo.get_by_id(instrument_id)
        if record is None:
            raise NotFoundError("Instrument", str(instrument_id))
        return _to_instrument(record)

    async def get_by_ticker(self, ticker: str) -> Instrument:
        record = await self._repo.get_by_ticker(ticker)
        if record is None:
            raise NotFoundError("Instrument", ticker)
        return _to_instrument(record)

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
    ) -> list[Instrument]:
        records = await self._repo.get_all_active(asset_class)
        return [_to_instrument(r) for r in records]

    async def search(self, query: str, limit: int = 20, *, offset: int = 0) -> list[Instrument]:
        records = await self._repo.search(query, limit, offset=offset)
        return [_to_instrument(r) for r in records]
