"""Auth protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.modules.platform.interfaces.fund import FundInfo
    from app.shared.auth.request_context import RequestContext


class AuthReader(Protocol):
    """Authentication interface exposed to other modules."""

    async def authenticate_jwt(
        self, token: str, *, fund_slug: str | None = None
    ) -> RequestContext: ...

    async def authenticate_api_key(self, raw_key: str) -> RequestContext: ...

    async def get_user_funds(self, user_id: str) -> list[FundInfo]: ...
