"""Platform SQLAlchemy models — re-exports for package compatibility."""

from app.modules.platform.models.api_key import APIKeyRecord
from app.modules.platform.models.audit_log import (
    PLATFORM_ENTITIES,
    AuditLogRecord,
    audit_log_immutable_fn,
    audit_log_no_delete,
    audit_log_no_truncate,
    audit_log_no_update,
)
from app.modules.platform.models.customer import CustomerRecord, CustomerStatus, CustomerType
from app.modules.platform.models.fund import FundRecord, FundStatus
from app.modules.platform.models.investor import InvestorRecord
from app.modules.platform.models.operator import OperatorRecord
from app.modules.platform.models.portfolio import PortfolioRecord
from app.modules.platform.models.servicing_edge import ServicingEdgeRecord, ServicingEdgeStatus
from app.modules.platform.models.user import UserRecord
from app.shared.models import Base as Base

__all__ = [
    "APIKeyRecord",
    "AuditLogRecord",
    "Base",
    "CustomerRecord",
    "CustomerStatus",
    "CustomerType",
    "FundRecord",
    "FundStatus",
    "InvestorRecord",
    "OperatorRecord",
    "PLATFORM_ENTITIES",
    "PortfolioRecord",
    "ServicingEdgeRecord",
    "ServicingEdgeStatus",
    "UserRecord",
    "audit_log_immutable_fn",
    "audit_log_no_delete",
    "audit_log_no_truncate",
    "audit_log_no_update",
]
