"""Platform repository package — re-exports all repository classes."""

from app.modules.platform.repositories.api_key import APIKeyRepository
from app.modules.platform.repositories.audit import AuditLogRepository, _compute_hash
from app.modules.platform.repositories.customer import CustomerRepository
from app.modules.platform.repositories.fund import FundRepository
from app.modules.platform.repositories.operator import OperatorRepository
from app.modules.platform.repositories.portfolio import PortfolioRepository
from app.modules.platform.repositories.servicing_edge import ServicingEdgeRepository
from app.modules.platform.repositories.user import UserRepository

__all__ = [
    "APIKeyRepository",
    "AuditLogRepository",
    "CustomerRepository",
    "FundRepository",
    "OperatorRepository",
    "PortfolioRepository",
    "ServicingEdgeRepository",
    "UserRepository",
    "_compute_hash",
]
