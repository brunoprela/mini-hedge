"""Platform services package — re-exports all service classes."""

from app.modules.platform.services.access import AccessGrantService
from app.modules.platform.services.admin import AdminService
from app.modules.platform.services.auth import AuthService
from app.modules.platform.services.fund import FundAdminService
from app.modules.platform.services.operator import OperatorAdminService
from app.modules.platform.services.user import UserAdminService

__all__ = [
    "AccessGrantService",
    "AdminService",
    "AuthService",
    "FundAdminService",
    "OperatorAdminService",
    "UserAdminService",
]
