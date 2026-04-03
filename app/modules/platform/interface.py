"""Platform public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

if TYPE_CHECKING:
    from app.shared.request_context import RequestContext


class FundInfo(BaseModel):
    """Fund summary returned by user fund listing."""

    model_config = ConfigDict(frozen=True)

    fund_slug: str
    fund_name: str
    role: str


class PortfolioInfo(BaseModel):
    """Portfolio summary for listing."""

    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str
    strategy: str | None
    fund_id: str


# ---------------------------------------------------------------------------
# Admin DTOs
# ---------------------------------------------------------------------------


class UserInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_active: bool


class OperatorInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_active: bool
    platform_role: str | None = None


class FundDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str
    status: str
    base_currency: str


class FundAccessGrant(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_type: str  # "user" or "operator"
    user_id: str
    relation: str
    relation_type: str = "role"  # "role" or "permission"
    display_name: str | None = None


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,48}[a-z0-9]$")

_USER_ROLES = frozenset(
    {
        "admin",
        "portfolio_manager",
        "analyst",
        "risk_manager",
        "compliance",
        "viewer",
    }
)
_USER_PERMISSIONS = frozenset(
    {
        "can_read_instruments",
        "can_write_instruments",
        "can_read_prices",
        "can_read_positions",
        "can_write_positions",
        "can_execute_trades",
        "can_read_fund",
        "can_manage_fund",
    }
)
_USER_RELATIONS = _USER_ROLES | _USER_PERMISSIONS
_OPERATOR_RELATIONS = frozenset({"ops_full", "ops_read"})
_VALID_RELATIONS = _USER_RELATIONS | _OPERATOR_RELATIONS


class _AccessRequestBase(BaseModel):
    user_type: Literal["user", "operator"]
    user_id: str
    relation: str

    @field_validator("user_id")
    @classmethod
    def _valid_uuid(cls, v: str) -> str:
        UUID(v)  # raises ValueError if invalid
        return v

    @field_validator("relation")
    @classmethod
    def _valid_relation(cls, v: str, info: object) -> str:
        if v not in _VALID_RELATIONS:
            raise ValueError(f"Invalid relation: {v}")
        return v


class AccessGrantRequest(_AccessRequestBase):
    pass


class AccessRevokeRequest(_AccessRequestBase):
    pass


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 200:
            raise ValueError("Name must be 1-200 characters")
        return v


class CreateOperatorRequest(BaseModel):
    email: EmailStr
    name: str
    platform_role: Literal["ops_admin", "ops_viewer"] = "ops_viewer"

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 200:
            raise ValueError("Name must be 1-200 characters")
        return v


class CreateFundRequest(BaseModel):
    slug: str
    name: str
    base_currency: Literal["USD", "EUR", "GBP", "JPY", "CHF"] = "USD"

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Slug must be 3-50 chars, lowercase alphanumeric "
                "with hyphens, starting with a letter"
            )
        return v


class UpdateUserRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class UpdateOperatorRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    platform_role: str | None = None


class UpdateFundRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class AuditEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    event_id: str
    event_type: str
    actor_id: str | None
    actor_type: str | None
    fund_slug: str | None
    payload: dict
    created_at: str


class AuditPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[AuditEntry]
    total: int
    limit: int
    offset: int


class UserPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[UserInfo]
    total: int
    limit: int
    offset: int


class OperatorPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[OperatorInfo]
    total: int
    limit: int
    offset: int


class FundPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[FundDetail]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class AuthReader(Protocol):
    """Authentication interface exposed to other modules."""

    async def authenticate_jwt(
        self, token: str, *, fund_slug: str | None = None
    ) -> RequestContext: ...

    async def authenticate_api_key(self, raw_key: str) -> RequestContext: ...

    async def get_user_funds(self, user_id: str) -> list[FundInfo]: ...
