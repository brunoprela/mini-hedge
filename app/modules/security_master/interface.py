"""Security master public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.shared.types import AssetClass

# Re-export so existing consumers keep working
__all__ = ["AssetClass", "Instrument", "SecurityMasterReader"]


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    ticker: str
    asset_class: AssetClass
    currency: str
    exchange: str
    country: str
    sector: str | None = None
    industry: str | None = None
    is_active: bool = True
    listed_date: date | None = None


# --- Protocol (structural contract for other modules) ---


class SecurityMasterReader(Protocol):
    """Read interface exposed to other modules."""

    async def get_by_id(self, instrument_id: UUID) -> Instrument: ...

    async def get_by_ticker(self, ticker: str) -> Instrument: ...

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
    ) -> list[Instrument]: ...

    async def search(self, query: str, limit: int = 20) -> list[Instrument]: ...
