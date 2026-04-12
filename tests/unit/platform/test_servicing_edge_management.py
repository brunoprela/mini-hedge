"""Unit tests for ServicingEdge management — repo methods, service, and DTOs."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.platform.interfaces.servicing_edge import (
    CreateServicingEdgeRequest,
    ServicingEdgeInfo,
    UpdateScopedRolesRequest,
)
from app.modules.platform.models.servicing_edge import (
    ServicingEdgeRecord,
    ServicingEdgeStatus,
)


class TestServicingEdgeDTOs:
    def test_create_request(self) -> None:
        req = CreateServicingEdgeRequest(
            admin_customer_id="admin-1",
            client_customer_id="client-1",
            scoped_roles=["analyst", "viewer"],
        )
        assert req.admin_customer_id == "admin-1"
        assert len(req.scoped_roles) == 2

    def test_update_roles_request(self) -> None:
        req = UpdateScopedRolesRequest(scoped_roles=["portfolio_manager"])
        assert req.scoped_roles == ["portfolio_manager"]

    def test_info_from_record(self) -> None:
        now = datetime.now(UTC)
        record = ServicingEdgeRecord(
            id="edge-1",
            admin_customer_id="admin-1",
            client_customer_id="client-1",
            scoped_roles=["analyst"],
            status=ServicingEdgeStatus.ACTIVE,
            effective_from=now,
            effective_until=None,
            created_at=now,
        )
        info = ServicingEdgeInfo.model_validate(record)
        assert info.id == "edge-1"
        assert info.status == "active"
        assert info.scoped_roles == ["analyst"]


class TestServicingEdgeStatus:
    def test_enum_values(self) -> None:
        assert ServicingEdgeStatus.ACTIVE == "active"
        assert ServicingEdgeStatus.SUSPENDED == "suspended"
        assert ServicingEdgeStatus.TERMINATED == "terminated"

    def test_all_statuses(self) -> None:
        assert len(ServicingEdgeStatus) == 3
