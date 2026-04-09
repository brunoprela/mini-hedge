"""Platform bounded context — multi-tenant fund registry, users, and RBAC."""

from app.modules.platform.interfaces.auth import AuthReader
from app.modules.platform.interfaces.fund import FundDetail, FundInfo, PortfolioInfo
from app.modules.platform.interfaces.operator import OperatorInfo
from app.modules.platform.interfaces.user import UserInfo

__all__ = [
    "AuthReader",
    "FundDetail",
    "FundInfo",
    "OperatorInfo",
    "PortfolioInfo",
    "UserInfo",
]
