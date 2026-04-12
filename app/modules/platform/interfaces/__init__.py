"""Platform public interface — Protocol + value objects.

Other modules depend ONLY on this package, never on internals.
"""

from app.modules.platform.interfaces.access import (
    AccessGrantRequest,
    AccessRevokeRequest,
    FundAccessGrant,
)
from app.modules.platform.interfaces.audit import AuditEntry, AuditPage
from app.modules.platform.interfaces.customer import (
    CreateCustomerRequest,
    CustomerInfo,
    CustomerPage,
    UpdateCustomerRequest,
)
from app.modules.platform.interfaces.auth import AuthReader
from app.modules.platform.interfaces.fund import (
    CreateFundRequest,
    FundDetail,
    FundInfo,
    FundPage,
    PortfolioInfo,
    UpdateFundRequest,
)
from app.modules.platform.interfaces.operator import (
    CreateOperatorRequest,
    OperatorInfo,
    OperatorPage,
    UpdateOperatorRequest,
)
from app.modules.platform.interfaces.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserPage,
)

__all__ = [
    "AccessGrantRequest",
    "AccessRevokeRequest",
    "AuditEntry",
    "AuditPage",
    "AuthReader",
    "CreateCustomerRequest",
    "CreateFundRequest",
    "CreateOperatorRequest",
    "CreateUserRequest",
    "CustomerInfo",
    "CustomerPage",
    "FundAccessGrant",
    "FundDetail",
    "FundInfo",
    "FundPage",
    "OperatorInfo",
    "OperatorPage",
    "PortfolioInfo",
    "UpdateCustomerRequest",
    "UpdateFundRequest",
    "UpdateOperatorRequest",
    "UpdateUserRequest",
    "UserInfo",
    "UserPage",
]
