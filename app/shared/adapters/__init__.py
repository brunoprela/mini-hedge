"""Adapter protocols for external data sources.

These define the contracts that all adapters must implement -- mock-exchange,
Bloomberg, LSEG, FIX brokers, DTCC, etc. Modules depend ONLY on these
protocols, never on concrete adapter implementations.

Swapping mock-exchange for a production vendor means:
1. Write a new adapter implementing the relevant Protocol
2. Register it in adapter_factory.py
3. Set the env var (e.g., BROKER_ADAPTER=bloomberg)
4. Zero changes to any module code
"""

from app.shared.adapters.alt_data import AltDataProvider, AltDataRecord, SentimentRecord
from app.shared.adapters.broker import BrokerAdapter, OrderAcknowledgement, OrderStatusReport
from app.shared.adapters.corporate_actions import CorporateAction, CorporateActionsAdapter
from app.shared.adapters.fund_admin import FundAdminAdapter
from app.shared.adapters.kyc import KYCScreeningAdapter
from app.shared.adapters.llm import LLMAdapter, LLMResponse
from app.shared.adapters.market_data import MarketDataAdapter
from app.shared.adapters.reference_data import ExternalInstrument, ReferenceDataAdapter

__all__ = [
    "AltDataProvider",
    "AltDataRecord",
    "BrokerAdapter",
    "CorporateAction",
    "CorporateActionsAdapter",
    "ExternalInstrument",
    "FundAdminAdapter",
    "KYCScreeningAdapter",
    "LLMAdapter",
    "LLMResponse",
    "MarketDataAdapter",
    "OrderAcknowledgement",
    "OrderStatusReport",
    "ReferenceDataAdapter",
    "SentimentRecord",
]
