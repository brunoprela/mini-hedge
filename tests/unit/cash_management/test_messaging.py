"""Unit tests for SettlementMessenger — SWIFT-like message generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.modules.cash_management.core.messaging import (
    SettlementMessageType,
    SettlementMessenger,
)


def _make_settlement(
    amount: Decimal = Decimal("-5000"),
    currency: str = "USD",
    instrument_id: str = "AAPL",
    settlement_date: date = date(2025, 4, 15),
) -> MagicMock:
    s = MagicMock()
    s.settlement_amount = amount
    s.currency = currency
    s.instrument_id = instrument_id
    s.settlement_date = settlement_date
    return s


class TestGeneratePaymentInstruction:
    def test_outgoing_payment_is_mt103(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(Decimal("-10000"))

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "Goldman Sachs")

        assert msg.message_type == SettlementMessageType.MT103
        assert msg.sender_bic == "MNHDUS33XXX"
        assert msg.receiver_bic == "GSINUS33XXX"
        assert msg.amount == Decimal("10000")
        assert msg.ordering_institution == "Mini Hedge Fund"
        assert msg.beneficiary_institution == "Goldman Sachs"

    def test_incoming_payment_is_mt210(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(Decimal("5000"))

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "Goldman Sachs")

        assert msg.message_type == SettlementMessageType.MT210
        assert msg.sender_bic == "GSINUS33XXX"
        assert msg.receiver_bic == "MNHDUS33XXX"
        assert msg.amount == Decimal("5000")
        assert msg.ordering_institution == "Goldman Sachs"

    def test_value_date_set_from_settlement(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(settlement_date=date(2025, 7, 1))

        msg = messenger.generate_payment_instruction(settlement, "JPMUS33XXX", "JP Morgan")

        assert msg.value_date == date(2025, 7, 1)

    def test_currency_preserved(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(currency="EUR")

        msg = messenger.generate_payment_instruction(settlement, "DEUTDEFFXXX", "Deutsche Bank")

        assert msg.currency == "EUR"

    def test_reference_populated(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement()

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "GS")

        assert msg.reference.startswith("REF")
        assert len(msg.reference) > 3

    def test_raw_message_populated(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement()

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "GS")

        assert msg.raw_message != ""
        assert "MT103" in msg.raw_message or "MT210" in msg.raw_message

    def test_custom_bic_and_name(self) -> None:
        messenger = SettlementMessenger(our_bic="CUSTUS33XXX", our_name="Custom Fund")
        settlement = _make_settlement(Decimal("-1000"))

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "GS")

        assert msg.sender_bic == "CUSTUS33XXX"
        assert msg.ordering_institution == "Custom Fund"


class TestGenerateConfirmation:
    def test_debit_confirmation_is_mt900(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(Decimal("-5000"))

        msg = messenger.generate_confirmation(settlement, is_debit=True)

        assert msg.message_type == SettlementMessageType.MT900
        assert msg.amount == Decimal("5000")
        assert "Debit" in msg.details

    def test_credit_confirmation_is_mt910(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(Decimal("5000"))

        msg = messenger.generate_confirmation(settlement, is_debit=False)

        assert msg.message_type == SettlementMessageType.MT910
        assert msg.amount == Decimal("5000")
        assert "Credit" in msg.details

    def test_confirmation_reference_starts_with_cnf(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement()

        msg = messenger.generate_confirmation(settlement, is_debit=True)

        assert msg.reference.startswith("CNF")


class TestFormatSwiftBlock:
    def test_contains_required_tags(self) -> None:
        messenger = SettlementMessenger()
        settlement = _make_settlement(Decimal("-1000"), "USD")

        msg = messenger.generate_payment_instruction(settlement, "GSINUS33XXX", "GS")

        raw = msg.raw_message
        assert ":20:" in raw  # reference
        assert ":32A:" in raw  # value date + amount
        assert ":50K:" in raw  # ordering institution
        assert ":59:" in raw  # beneficiary
        assert ":70:" in raw  # details
        assert "USD" in raw
