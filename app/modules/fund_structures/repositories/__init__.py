"""Fund structures repository package."""

from app.modules.fund_structures.repositories.fund_of_funds import FundOfFundsRepository
from app.modules.fund_structures.repositories.master_feeder import MasterFeederRepository
from app.modules.fund_structures.repositories.strategy_book import StrategyBookRepository

__all__ = [
    "FundOfFundsRepository",
    "MasterFeederRepository",
    "StrategyBookRepository",
]
