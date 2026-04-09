"""User-related DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    is_active: bool


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


class UpdateUserRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class UserPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[UserInfo]
    total: int
    limit: int
    offset: int
