"""FundAdminAdapter protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from decimal import Decimal


class FundAdminAdapter(Protocol):
    """Vendor-agnostic fund administrator interface.

    The fund admin independently tracks positions, cash, and NAV from
    trade confirmations.  Used in three-way reconciliation:
    internal vs broker vs administrator.

    Implementations: mock-exchange fund admin, Citco, SS&C.
    """

    async def get_positions(self) -> dict[str, Decimal]:
        """Return instrument_id -> quantity from the admin's books."""
        ...

    async def get_cash_balances(self) -> dict[str, Decimal]:
        """Return currency -> cash balance from the admin's books."""
        ...

    async def register_subscription(
        self, request_id: str, investor_id: str, amount: Decimal
    ) -> str:
        """Register a subscription and return a wire reference."""
        ...

    async def confirm_wire_receipt(self, wire_reference: str) -> bool:
        """Confirm bank wire receipt. Returns True on success."""
        ...

    async def register_redemption(self, request_id: str, investor_id: str, amount: Decimal) -> None:
        """Register a pending redemption payment."""
        ...

    async def send_redemption_payment(self, request_id: str) -> str | None:
        """Send a wire for a redemption. Returns payment reference."""
        ...
