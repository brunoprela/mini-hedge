"""Settlement message generation -- SWIFT-like instruction messages.

Generates MT103 (customer credit transfer), MT202 (institution transfer),
MT210 (notice to receive), MT900 (debit confirmation), and MT910 (credit
confirmation) formatted messages.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.cash_management.models import CashSettlementRecord

ZERO = Decimal(0)


class SettlementMessageType(StrEnum):
    MT103 = "MT103"  # Single customer credit transfer
    MT202 = "MT202"  # General financial institution transfer
    MT210 = "MT210"  # Notice to receive
    MT900 = "MT900"  # Confirmation of debit
    MT910 = "MT910"  # Confirmation of credit


class SettlementMessage(BaseModel):
    """A SWIFT-like settlement instruction message."""

    model_config = ConfigDict(frozen=True)

    message_type: SettlementMessageType
    reference: str
    sender_bic: str
    receiver_bic: str
    value_date: date
    currency: str
    amount: Decimal
    ordering_institution: str
    beneficiary_institution: str
    details: str
    raw_message: str  # The formatted SWIFT-like text block


class SettlementMessenger:
    """Generates settlement instruction messages."""

    def __init__(
        self,
        our_bic: str = "MNHDUS33XXX",
        our_name: str = "Mini Hedge Fund",
    ) -> None:
        self._our_bic = our_bic
        self._our_name = our_name

    def generate_payment_instruction(
        self,
        settlement: CashSettlementRecord,
        counterparty_bic: str,
        counterparty_name: str,
    ) -> SettlementMessage:
        """Generate MT103 for outgoing payment or MT210 for incoming."""
        amount = settlement.settlement_amount
        reference = f"REF{uuid4().hex[:12].upper()}"

        if amount < ZERO:
            # Outgoing payment -- MT103
            msg_type = SettlementMessageType.MT103
            sender_bic = self._our_bic
            receiver_bic = counterparty_bic
            ordering = self._our_name
            beneficiary = counterparty_name
            details = f"Payment for settlement of {settlement.instrument_id}"
            abs_amount = abs(amount)
        else:
            # Incoming -- MT210 notice to receive
            msg_type = SettlementMessageType.MT210
            sender_bic = counterparty_bic
            receiver_bic = self._our_bic
            ordering = counterparty_name
            beneficiary = self._our_name
            details = f"Expected receipt for settlement of {settlement.instrument_id}"
            abs_amount = amount

        msg = SettlementMessage(
            message_type=msg_type,
            reference=reference,
            sender_bic=sender_bic,
            receiver_bic=receiver_bic,
            value_date=settlement.settlement_date,
            currency=settlement.currency,
            amount=abs_amount,
            ordering_institution=ordering,
            beneficiary_institution=beneficiary,
            details=details,
            raw_message="",  # placeholder, filled below
        )
        raw = self.format_swift_block(msg)
        # Reconstruct with raw_message populated
        return msg.model_copy(update={"raw_message": raw})

    def generate_confirmation(
        self,
        settlement: CashSettlementRecord,
        is_debit: bool,
    ) -> SettlementMessage:
        """Generate MT900 (debit) or MT910 (credit) confirmation."""
        reference = f"CNF{uuid4().hex[:12].upper()}"
        abs_amount = abs(settlement.settlement_amount)

        if is_debit:
            msg_type = SettlementMessageType.MT900
            details = f"Debit confirmation for {settlement.instrument_id}"
        else:
            msg_type = SettlementMessageType.MT910
            details = f"Credit confirmation for {settlement.instrument_id}"

        msg = SettlementMessage(
            message_type=msg_type,
            reference=reference,
            sender_bic=self._our_bic,
            receiver_bic=self._our_bic,
            value_date=settlement.settlement_date,
            currency=settlement.currency,
            amount=abs_amount,
            ordering_institution=self._our_name,
            beneficiary_institution=self._our_name,
            details=details,
            raw_message="",
        )
        raw = self.format_swift_block(msg)
        return msg.model_copy(update={"raw_message": raw})

    def format_swift_block(self, msg: SettlementMessage) -> str:
        """Format message as SWIFT-like text block."""
        value_date_str = msg.value_date.strftime("%y%m%d")
        lines = [
            f"{{1:F01{msg.sender_bic}0000000000}}",
            f"{{2:O{msg.message_type.value}0000{msg.receiver_bic}0000000000000000N}}",
            "{4:",
            f":20:{msg.reference}",
            ":23B:CRED",
            f":32A:{value_date_str}{msg.currency}{msg.amount}",
            f":50K:/{msg.ordering_institution}",
            f":59:/{msg.beneficiary_institution}",
            f":70:{msg.details}",
            ":71A:SHA",
            "-}",
        ]
        return "\n".join(lines)
