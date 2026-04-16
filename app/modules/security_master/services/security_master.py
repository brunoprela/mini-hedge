"""Security master business logic — implements the SecurityMasterReader protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.interfaces import AssetClass, Instrument
from app.modules.security_master.models.instrument import InstrumentRecord
from app.modules.security_master.repositories import IdentifierRepository, InstrumentRepository
from app.shared.audit.events import AuditEventType
from app.shared.errors import NotFoundError
from app.shared.events import BaseEvent
from app.shared.schema_registry import shared_topic

if TYPE_CHECKING:
    from app.modules.security_master.models.identifier import IdentifierType
    from app.shared.events import EventBus

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

    def __init__(
        self,
        *,
        repository: InstrumentRepository,
        identifier_repo: IdentifierRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._instrument_repo = repository
        self._identifier_repo = identifier_repo
        self._event_bus = event_bus

    async def get_by_id(
        self, instrument_id: UUID, *, session: AsyncSession | None = None
    ) -> Instrument:
        record = await self._instrument_repo.get_by_id(instrument_id, session=session)
        if record is None:
            raise NotFoundError("Instrument", str(instrument_id))
        return _to_instrument(record)

    async def get_by_ticker(
        self, ticker: str, *, session: AsyncSession | None = None
    ) -> Instrument:
        record = await self._instrument_repo.get_by_ticker(ticker, session=session)
        if record is None:
            raise NotFoundError("Instrument", ticker)
        return _to_instrument(record)

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[Instrument]:
        records = await self._instrument_repo.get_all_active(asset_class, session=session)
        return [_to_instrument(r) for r in records]

    async def search(
        self, query: str, limit: int = 20, *, offset: int = 0, session: AsyncSession | None = None
    ) -> list[Instrument]:
        records = await self._instrument_repo.search(query, limit, offset=offset, session=session)
        return [_to_instrument(r) for r in records]

    async def resolve(
        self,
        id_type: IdentifierType | str,
        id_value: str,
        *,
        session: AsyncSession | None = None,
    ) -> Instrument:
        """Resolve any identifier (ISIN, CUSIP, SEDOL, FIGI, etc.) to a canonical instrument.

        Falls back to ticker lookup when id_type is "ticker" or no identifier repo is configured.
        """
        id_type_str = str(id_type)

        # Fast path: ticker lookup uses the existing indexed column directly
        if id_type_str == "ticker":
            return await self.get_by_ticker(id_value, session=session)

        if self._identifier_repo is None:
            raise NotFoundError("Instrument", f"{id_type_str}:{id_value}")

        record = await self._identifier_repo.resolve(id_type_str, id_value, session=session)
        if record is None:
            raise NotFoundError("Instrument", f"{id_type_str}:{id_value}")
        return _to_instrument(record)

    async def create_instrument(
        self,
        *,
        name: str,
        ticker: str,
        asset_class: AssetClass,
        currency: str,
        exchange: str,
        country: str,
        sector: str | None = None,
        industry: str | None = None,
        session: AsyncSession | None = None,
    ) -> Instrument:
        """Create a new instrument and publish an event."""
        record = InstrumentRecord(
            name=name,
            ticker=ticker.upper(),
            asset_class=asset_class.value,
            currency=currency,
            exchange=exchange,
            country=country,
            sector=sector,
            industry=industry,
        )
        saved = await self._instrument_repo.insert(record, session=session)
        instrument = _to_instrument(saved)
        await self._publish_instrument_event(
            AuditEventType.INSTRUMENT_CREATED,
            instrument,
        )
        logger.info("instrument_created", ticker=ticker, id=saved.id)
        return instrument

    async def update_instrument(
        self,
        instrument_id: UUID,
        updates: dict[str, object],
        *,
        session: AsyncSession | None = None,
    ) -> Instrument:
        """Update an instrument and publish an event."""
        record = await self._instrument_repo.update(
            str(instrument_id), updates, session=session
        )
        if record is None:
            raise NotFoundError("Instrument", str(instrument_id))
        instrument = _to_instrument(record)
        await self._publish_instrument_event(
            AuditEventType.INSTRUMENT_UPDATED,
            instrument,
            changes=list(updates.keys()),
        )
        logger.info("instrument_updated", ticker=instrument.ticker, id=str(instrument_id))
        return instrument

    async def _publish_instrument_event(
        self,
        event_type: AuditEventType,
        instrument: Instrument,
        *,
        changes: list[str] | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        data: dict[str, object] = {
            "instrument_id": str(instrument.id),
            "ticker": instrument.ticker,
            "asset_class": str(instrument.asset_class),
            "currency": instrument.currency,
        }
        if changes:
            data["changed_fields"] = changes
        event = BaseEvent(event_type=event_type, data=data)
        topic_stem = "instruments.created" if event_type == AuditEventType.INSTRUMENT_CREATED else "instruments.updated"
        await self._event_bus.publish(shared_topic(topic_stem), event)
