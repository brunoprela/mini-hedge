"""Access/role request DTOs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

_USER_ROLES = frozenset(
    {
        "admin",
        "portfolio_manager",
        "analyst",
        "risk_manager",
        "compliance_officer",
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
        "can_read_orders",
        "can_create_orders",
        "can_cancel_orders",
        "can_read_compliance",
        "can_manage_compliance",
        "can_read_exposure",
    }
)
_USER_RELATIONS = _USER_ROLES | _USER_PERMISSIONS
_OPERATOR_RELATIONS = frozenset({"ops_full", "ops_read"})
_VALID_RELATIONS = _USER_RELATIONS | _OPERATOR_RELATIONS


class FundAccessGrant(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_type: str  # "user" or "operator"
    user_id: str
    relation: str
    relation_type: str = "role"  # "role" or "permission"
    display_name: str | None = None


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
