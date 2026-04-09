"""Platform bounded context — multi-tenant fund registry, users, and RBAC."""

from app.modules.platform.interface import (
    AuthReader,
    FundDetail,
    FundInfo,
    OperatorInfo,
    PortfolioInfo,
    UserInfo,
)

__all__ = [
    "AuthReader",
    "FundDetail",
    "FundInfo",
    "OperatorInfo",
    "PortfolioInfo",
    "UserInfo",
]
