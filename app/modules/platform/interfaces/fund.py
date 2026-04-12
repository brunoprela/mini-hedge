"""Fund-related DTOs."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class FundInfo(BaseModel):
    """Fund summary returned by user fund listing."""

    model_config = ConfigDict(frozen=True)

    fund_slug: str
    fund_name: str
    role: str
    customer_id: str | None = None
    customer_name: str | None = None


class PortfolioInfo(BaseModel):
    """Portfolio summary for listing."""

    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str
    strategy: str | None
    fund_id: str


class FundDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str
    status: str
    base_currency: str


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,48}[a-z0-9]$")


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


class UpdateFundRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class FundPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[FundDetail]
    total: int
    limit: int
    offset: int
