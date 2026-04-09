"""Operator-related DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class OperatorInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_active: bool
    platform_role: str | None = None


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


class UpdateOperatorRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    platform_role: str | None = None


class OperatorPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[OperatorInfo]
    total: int
    limit: int
    offset: int
