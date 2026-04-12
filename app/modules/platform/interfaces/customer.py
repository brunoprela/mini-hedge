"""Customer-related DTOs."""

from pydantic import BaseModel, ConfigDict, field_validator


class CustomerInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    slug: str
    name: str
    customer_type: str
    status: str


class CreateCustomerRequest(BaseModel):
    slug: str
    name: str
    customer_type: str = "direct_fund"

    @field_validator("slug")
    @classmethod
    def _slug_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or len(v) > 64:
            raise ValueError("Slug must be 1-64 characters")
        return v

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("Name must be 1-255 characters")
        return v

    @field_validator("customer_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in ("direct_fund", "fund_administrator"):
            raise ValueError("customer_type must be 'direct_fund' or 'fund_administrator'")
        return v


class UpdateCustomerRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class CustomerPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[CustomerInfo]
    total: int
    limit: int
    offset: int
