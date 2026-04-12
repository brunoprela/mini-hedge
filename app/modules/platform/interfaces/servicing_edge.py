"""DTOs for servicing edge management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateServicingEdgeRequest(BaseModel):
    admin_customer_id: str
    client_customer_id: str
    scoped_roles: list[str]


class UpdateScopedRolesRequest(BaseModel):
    scoped_roles: list[str]


class ServicingEdgeInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_customer_id: str
    client_customer_id: str
    scoped_roles: list[str]
    status: str
    effective_from: datetime
    effective_until: datetime | None
    created_at: datetime
