"""MarketDataAdapter protocol."""

from __future__ import annotations

from typing import Protocol


class MarketDataAdapter(Protocol):
    """Vendor-agnostic market data source.

    Implementations: mock-exchange, Bloomberg BLPAPI HTTP, LSEG RDP, Massive.
    """

    async def start_streaming(self, instruments: list[str]) -> None:
        """Begin pushing prices to the platform (e.g. via Kafka)."""
        ...

    async def stop_streaming(self) -> None: ...
