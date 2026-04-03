"""Re-exports for backwards compatibility.

Each repository class now lives in its own module. Import from there directly.
"""

from app.modules.platform.api_key_repository import APIKeyRepository
from app.modules.platform.fund_repository import FundRepository
from app.modules.platform.portfolio_repository import PortfolioRepository
from app.modules.platform.user_repository import UserRepository

__all__ = [
    "APIKeyRepository",
    "FundRepository",
    "PortfolioRepository",
    "UserRepository",
]
