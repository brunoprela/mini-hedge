"""Platform public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.shared.request_context import RequestContext


class FundInfo(BaseModel):
    """Fund summary returned by user fund listing."""

    model_config = ConfigDict(frozen=True)

    fund_slug: str
    fund_name: str
    role: str


class AuthReader(Protocol):
    """Authentication interface exposed to other modules."""

    async def authenticate_jwt(
        self, token: str, *, fund_slug: str | None = None
    ) -> RequestContext | None: ...

    async def authenticate_api_key(self, raw_key: str) -> RequestContext | None: ...

    async def get_user_funds(self, user_id: str) -> list[FundInfo]: ...
