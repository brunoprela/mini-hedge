"""Access grant service — manages fund-level access via OpenFGA."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from openfga_sdk.client.models import ClientTuple

from app.modules.platform.interface import AuditEntry, AuditPage, FundAccessGrant
from app.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.auth_service import AuthService
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.operator_repository import OperatorRepository
    from app.modules.platform.user_repository import UserRepository
    from app.shared.fga import FGAClient
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()

# FGA relation names for reading fund access
_FUND_USER_ROLES = [
    "admin",
    "portfolio_manager",
    "analyst",
    "risk_manager",
    "compliance_officer",
    "viewer",
]
_FUND_USER_PERMISSIONS = [
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
]
_FUND_OPERATOR_RELATIONS = ["ops_full", "ops_read"]


class AccessGrantService:
    """Manage fund-level access grants and audit log queries."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        operator_repo: OperatorRepository,
        fund_repo: FundRepository,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
        auth_service: AuthService | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._operator_repo = operator_repo
        self._fund_repo = fund_repo
        self._fga_client = fga_client
        self._audit_repo = audit_repo
        self._auth_service = auth_service

    async def list_fund_access(
        self, fund_id: str, *, session: AsyncSession | None = None
    ) -> list[FundAccessGrant]:
        """List all access grants on a fund via a single FGA read."""
        tuples = await self._fga_client.read_tuples(object=f"fund:{fund_id}")

        # Collect IDs for batch display-name lookup
        user_ids: set[str] = set()
        operator_ids: set[str] = set()
        for fga_user, _relation, _obj in tuples:
            if fga_user.startswith("user:"):
                user_ids.add(fga_user.removeprefix("user:"))
            elif fga_user.startswith("operator:"):
                operator_ids.add(fga_user.removeprefix("operator:"))

        # Build display-name maps
        names: dict[str, str] = {}
        for uid in user_ids:
            record = await self._user_repo.get_by_id(uid, session=session)
            if record:
                names[f"user:{uid}"] = record.name
        for oid in operator_ids:
            record = await self._operator_repo.get_by_id(oid, session=session)
            if record:
                names[f"operator:{oid}"] = record.name

        permission_set = set(_FUND_USER_PERMISSIONS)
        grants: list[FundAccessGrant] = []
        for fga_user, relation, _obj in tuples:
            if ":" not in fga_user:
                continue
            user_type, subject_id = fga_user.split(":", 1)
            if user_type not in ("user", "operator"):
                continue
            grants.append(
                FundAccessGrant(
                    user_type=user_type,
                    user_id=subject_id,
                    relation=relation,
                    relation_type="permission" if relation in permission_set else "role",
                    display_name=names.get(fga_user),
                )
            )

        return grants

    async def grant_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> None:
        """Grant a user or operator a relation on a fund via FGA."""
        fund = await self._fund_repo.get_by_id(fund_id, session=session)
        if fund is None:
            raise NotFoundError("Fund", fund_id)
        # Validate that the subject exists
        if (
            user_type == "user"
            and await self._user_repo.get_by_id(user_id, session=session) is None
        ):
            raise NotFoundError("User", user_id)
        elif (
            user_type == "operator"
            and await self._operator_repo.get_by_id(user_id, session=session) is None
        ):
            raise NotFoundError("Operator", user_id)
        await self._fga_client.write_tuples(
            [
                ClientTuple(
                    user=f"{user_type}:{user_id}",
                    relation=relation,
                    object=f"fund:{fund_id}",
                )
            ]
        )
        # Invalidate auth cache so the change takes effect immediately
        if user_type == "user" and self._auth_service is not None:
            self._auth_service.invalidate_fga_cache(user_id, fund_id)

        await self._audit_repo.insert_admin_event(
            event_type="admin.access.granted",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            fund_slug=fund.slug,
            payload={
                "fund_id": fund_id,
                "user_type": user_type,
                "user_id": user_id,
                "relation": relation,
            },
            session=session,
        )

    async def revoke_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        request_context: RequestContext,
        session: AsyncSession | None = None,
    ) -> None:
        """Revoke a user or operator's relation on a fund via FGA."""
        fund = await self._fund_repo.get_by_id(fund_id, session=session)
        if fund is None:
            raise NotFoundError("Fund", fund_id)
        await self._fga_client.delete_tuples(
            [
                ClientTuple(
                    user=f"{user_type}:{user_id}",
                    relation=relation,
                    object=f"fund:{fund_id}",
                )
            ]
        )
        # Invalidate auth cache so the change takes effect immediately
        if user_type == "user" and self._auth_service is not None:
            self._auth_service.invalidate_fga_cache(user_id, fund_id)

        await self._audit_repo.insert_admin_event(
            event_type="admin.access.revoked",
            actor_id=request_context.actor_id,
            actor_type=request_context.actor_type.value,
            fund_slug=fund.slug,
            payload={
                "fund_id": fund_id,
                "user_type": user_type,
                "user_id": user_id,
                "relation": relation,
            },
            session=session,
        )

    async def list_audit(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> AuditPage:
        records, total = await self._audit_repo.query(
            fund_slug=fund_slug,
            event_type=event_type,
            limit=limit,
            offset=offset,
            session=session,
        )
        items = [
            AuditEntry(
                id=r.id,
                event_id=r.event_id,
                event_type=r.event_type,
                actor_id=r.actor_id,
                actor_type=r.actor_type,
                fund_slug=r.fund_slug,
                payload=r.payload,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ]
        return AuditPage(items=items, total=total, limit=limit, offset=offset)
