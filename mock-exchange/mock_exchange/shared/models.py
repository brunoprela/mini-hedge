"""Shared Pydantic models used across mock-exchange modules."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


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
    avg_daily_volume: int = 10_000_000
    market_cap_usd: float = 100_000_000_000.0
    lot_size: int = 1
    tick_size: float = 0.01


class TradeTick(BaseModel):
    instrument_id: str
    price: Decimal
    quantity: int
    side: str  # "buy" | "sell"
    timestamp: datetime
    is_ambient: bool = False
    aggressor: str = "buyer"  # "buyer" | "seller" — who crossed the spread


class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: int


class OrderBookSnapshot(BaseModel):
    instrument_id: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime


class VWAPData(BaseModel):
    instrument_id: str
    vwap: Decimal
    cumulative_volume: int
    period_start: datetime
    period_end: datetime


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
    broker_id: str | None = None
    arrival_price: Decimal | None = None
    commission_bps: float | None = None
    spread_cost_bps: float | None = None


class BrokerInfo(BaseModel):
    broker_id: str
    name: str
    commission_bps: float
    latency_ms: int
    fill_rate: float
    sector_specializations: list[str]


class ScenarioStatus(BaseModel):
    active_scenario: str | None = None
    instruments: int = 0
    phase: str | None = None
    uptime_seconds: float = 0.0
