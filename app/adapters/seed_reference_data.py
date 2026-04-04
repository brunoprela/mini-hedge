"""Seed reference data adapter — wraps existing build_seed_records() for backward compat."""

from __future__ import annotations

from app.modules.security_master.seed import SEED_INSTRUMENTS
from app.shared.adapters import ExternalInstrument


class SeedReferenceDataAdapter:
    """ReferenceDataAdapter that returns instruments from the hardcoded seed data.

    Used when REFERENCE_DATA_SOURCE=seed to preserve the current
    behavior without requiring mock-exchange.
    """

    async def get_instrument(self, ticker: str) -> ExternalInstrument | None:
        for entry in SEED_INSTRUMENTS:
            if entry.get("ticker") == ticker:
                return self._to_external(entry)
        return None

    async def get_all_instruments(
        self, asset_class: str | None = None
    ) -> list[ExternalInstrument]:
        result = []
        for entry in SEED_INSTRUMENTS:
            if asset_class and str(entry.get("asset_class", "")) != asset_class:
                continue
            result.append(self._to_external(entry))
        return result

    @staticmethod
    def _to_external(entry: dict[str, object]) -> ExternalInstrument:
        return ExternalInstrument(
            ticker=str(entry.get("ticker", "")),
            name=str(entry.get("name", "")),
            asset_class=str(entry.get("asset_class", "")),
            currency=str(entry.get("currency", "")),
            exchange=str(entry.get("exchange", "")),
            country=str(entry.get("country", "")),
            sector=str(entry.get("sector", "")),
            industry=str(entry.get("industry", "")),
        )
