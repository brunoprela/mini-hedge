"""Fund structures models package."""

from app.modules.fund_structures.models.fund_of_funds_holding import FundOfFundsHoldingRecord
from app.modules.fund_structures.models.master_feeder_link import MasterFeederLinkRecord
from app.modules.fund_structures.models.strategy_book import StrategyBookRecord
from app.shared.models import Base as Base

__all__ = [
    "FundOfFundsHoldingRecord",
    "MasterFeederLinkRecord",
    "StrategyBookRecord",
]
