"""Audit-related DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuditEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    event_id: str
    event_type: str
    actor_id: str | None
    actor_type: str | None
    fund_slug: str | None
    payload: dict[str, object]
    created_at: str


class AuditPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[AuditEntry]
    total: int
    limit: int
    offset: int
