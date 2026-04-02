"""Shared value types used across bounded contexts."""

from decimal import Decimal
from enum import StrEnum
from typing import NewType


class AssetClass(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    OPTION = "option"
    FUTURE = "future"
    ETF = "etf"
    FX = "fx"
    SWAP = "swap"
    PRIVATE = "private"


# Semantic type aliases for clarity at module boundaries.
# InstrumentId is always a string (e.g. "AAPL"), but NewType lets mypy
# catch accidental misuse (passing a portfolio_id where instrument_id is expected).
InstrumentId = NewType("InstrumentId", str)

# Money is Decimal — never float for financial values.
Money = NewType("Money", Decimal)
