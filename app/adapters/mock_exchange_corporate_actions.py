"""Mock-exchange corporate actions adapter — fetches actions via HTTP."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import structlog

from app.shared.adapters import CorporateAction
from app.shared.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()


class MockExchangeCorporateActionsAdapter:
    """CorporateActionsAdapter backed by the mock-exchange service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._circuit = CircuitBreaker(
            "mock-exchange-corporate-actions",
            tracked_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )

    async def get_actions(
        self,
        instrument_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CorporateAction]:
        params: dict[str, str] = {}
        if instrument_id:
            params["instrument_id"] = instrument_id
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()

        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client,
            self._circuit(),
        ):
            resp = await client.get("/api/v1/corporate-actions", params=params)
            resp.raise_for_status()

        actions: list[CorporateAction] = []
        for item in resp.json():
            record_date_raw = item.get("record_date")
            pay_date_raw = item.get("pay_date")
            amount_raw = item.get("amount")
            actions.append(
                CorporateAction(
                    action_id=item["action_id"],
                    instrument_id=item["instrument_id"],
                    action_type=item["action_type"],
                    ex_date=date.fromisoformat(item["ex_date"]),
                    record_date=date.fromisoformat(record_date_raw) if record_date_raw else None,
                    pay_date=date.fromisoformat(pay_date_raw) if pay_date_raw else None,
                    amount=Decimal(amount_raw) if amount_raw else None,
                    currency=item.get("currency", "USD"),
                )
            )
        return actions
