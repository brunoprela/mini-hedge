"""CorporateActionsAdapter protocol and CorporateAction value object."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import date
    from decimal import Decimal


class CorporateAction:
    """Corporate action event from an external source."""

    __slots__ = (
        "action_id",
        "instrument_id",
        "action_type",
        "ex_date",
        "record_date",
        "pay_date",
        "amount",
        "currency",
    )

    def __init__(
        self,
        *,
        action_id: str,
        instrument_id: str,
        action_type: str,
        ex_date: date,
        record_date: date | None = None,
        pay_date: date | None = None,
        amount: Decimal | None = None,
        currency: str = "USD",
    ) -> None:
        self.action_id = action_id
        self.instrument_id = instrument_id
        self.action_type = action_type
        self.ex_date = ex_date
        self.record_date = record_date
        self.pay_date = pay_date
        self.amount = amount
        self.currency = currency


class CorporateActionsAdapter(Protocol):
    """Vendor-agnostic corporate actions source.

    Implementations: mock-exchange, LSEG RDP.
    """

    async def get_actions(
        self,
        instrument_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CorporateAction]: ...
