"""Shared Pydantic models used across mock-exchange modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


class PriceQuote(BaseModel):
    instrument_id: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    volume: int
    timestamp: datetime
    source: str = "mock-exchange"


class InstrumentInfo(BaseModel):
    ticker: str
    name: str
    asset_class: str
    currency: str
    exchange: str
    country: str
    sector: str
    industry: str
    annual_drift: float = 0.08
    annual_volatility: float = 0.25
    spread_bps: float = 10.0
    is_active: bool = True


class OrderAck(BaseModel):
    exchange_order_id: str
    client_order_id: str
    status: str  # acknowledged, rejected
    received_at: datetime


class FillReport(BaseModel):
    fill_id: str
    exchange_order_id: str
    client_order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal
    filled_at: datetime


class ScenarioStatus(BaseModel):
    active_scenario: str | None = None
    instruments: int = 0
    phase: str | None = None
    uptime_seconds: float = 0.0
