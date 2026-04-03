"""Admin service — manages users, operators, funds, and access grants.

All authorization writes go through OpenFGA. Identity records are managed
in PostgreSQL. Every mutation is audit-logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from openfga_sdk.client.models import ClientTuple

from app.modules.platform.interface import (
    AuditEntry,
    AuditPage,
    FundAccessGrant,
    FundDetail,
    OperatorInfo,
    UserInfo,
)
from app.modules.platform.models import (
    FundRecord,
    FundStatus,
    OperatorRecord,
    UserRecord,
)
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.auth_service import AuthService
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.operator_repository import OperatorRepository
    from app.modules.platform.user_repository import UserRepository
    from app.shared.events import EventBus
    from app.shared.fga import FGAClient
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()

# FGA relation names for reading fund access
_FUND_USER_RELATIONS = [
    "admin", "portfolio_manager", "analyst",
    "risk_manager", "compliance", "viewer",
]
_FUND_OPERATOR_RELATIONS = ["ops_full", "ops_read"]
_PLATFORM_ROLES = ["ops_admin", "ops_viewer"]


class AdminService:
    """Admin operations for platform management."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        operator_repo: OperatorRepository,
        fund_repo: FundRepository,
        fga_client: FGAClient,
        audit_repo: AuditLogRepository,
        engine: AsyncEngine | None = None,
        event_bus: EventBus | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._operator_repo = operator_repo
        self._fund_repo = fund_repo
        self._fga = fga_client
        self._audit = audit_repo
        self._engine = engine
        self._event_bus = event_bus
        self._auth_service = auth_service

    # ----- Users -----

    async def list_users(self) -> list[UserInfo]:
        records = await self._user_repo.get_all()
        return [_user_to_info(r) for r in records]

    async def create_user(
        self, *, email: str, name: str, actor: RequestContext
    ) -> UserInfo:
        existing = await self._user_repo.get_by_email(email)
        if existing is not None:
            raise ValidationError("User with this email already exists")
        record = UserRecord(email=email, name=name, is_active=True)
        await self._user_repo.insert(record)
        await self._audit.insert_admin_event(
            event_type="admin.user.created",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            payload={"email": email, "name": name, "user_id": record.id},
        )
        return _user_to_info(record)

    async def get_user(self, user_id: str) -> UserInfo:
        record = await self._user_repo.get_by_id(user_id)
        if record is None:
            raise NotFoundError("User", user_id)
        return _user_to_info(record)

    async def update_user(
        self,
        user_id: str,
        *,
        actor: RequestContext,
        **fields: object,
    ) -> UserInfo:
        record = await self._user_repo.update(user_id, **fields)
        if record is None:
            raise NotFoundError("User", user_id)
        await self._audit.insert_admin_event(
            event_type="admin.user.updated",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            payload={"user_id": user_id, "fields": {k: str(v) for k, v in fields.items()}},
        )
        return _user_to_info(record)

    # ----- Operators -----

    async def list_operators(self) -> list[OperatorInfo]:
        records = await self._operator_repo.get_all()
        result: list[OperatorInfo] = []
        for r in records:
            roles = await self._fga.list_relations(
                user=f"operator:{r.id}",
                object="platform:global",
                relations=_PLATFORM_ROLES,
            )
            role = "ops_admin" if "ops_admin" in roles else (roles[0] if roles else None)
            result.append(_operator_to_info(r, platform_role=role))
        return result

    async def create_operator(
        self,
        *,
        email: str,
        name: str,
        platform_role: str,
        actor: RequestContext,
    ) -> OperatorInfo:
        existing = await self._operator_repo.get_by_email(email)
        if existing is not None:
            raise ValidationError("Operator with this email already exists")
        record = OperatorRecord(email=email, name=name, is_active=True)
        await self._operator_repo.insert(record)
        # Grant platform role via FGA
        await self._fga.write_tuples([
            ClientTuple(
                user=f"operator:{record.id}",
                relation=platform_role,
                object="platform:global",
            )
        ])
        await self._audit.insert_admin_event(
            event_type="admin.operator.created",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            payload={
                "email": email, "name": name,
                "operator_id": record.id, "platform_role": platform_role,
            },
        )
        return _operator_to_info(record, platform_role=platform_role)

    async def update_operator(
        self,
        operator_id: str,
        *,
        actor: RequestContext,
        name: str | None = None,
        is_active: bool | None = None,
        platform_role: str | None = None,
    ) -> OperatorInfo:
        fields: dict[str, object] = {}
        if name is not None:
            fields["name"] = name
        if is_active is not None:
            fields["is_active"] = is_active
        record = await self._operator_repo.update(operator_id, **fields) if fields else None
        if record is None:
            record = await self._operator_repo.get_by_id(operator_id)
        if record is None:
            raise NotFoundError("Operator", operator_id)

        # Update platform role if requested
        if platform_role is not None:
            # Remove old roles, add new one
            old_roles = await self._fga.list_relations(
                user=f"operator:{operator_id}",
                object="platform:global",
                relations=_PLATFORM_ROLES,
            )
            if old_roles:
                await self._fga.delete_tuples([
                    ClientTuple(
                        user=f"operator:{operator_id}",
                        relation=r,
                        object="platform:global",
                    )
                    for r in old_roles
                ])
            await self._fga.write_tuples([
                ClientTuple(
                    user=f"operator:{operator_id}",
                    relation=platform_role,
                    object="platform:global",
                )
            ])

        await self._audit.insert_admin_event(
            event_type="admin.operator.updated",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            payload={"operator_id": operator_id, "fields": {k: str(v) for k, v in fields.items()}},
        )

        # Resolve current role for response
        roles = await self._fga.list_relations(
            user=f"operator:{operator_id}",
            object="platform:global",
            relations=_PLATFORM_ROLES,
        )
        role = "ops_admin" if "ops_admin" in roles else (roles[0] if roles else None)
        return _operator_to_info(record, platform_role=role)

    # ----- Funds -----

    async def list_funds(self) -> list[FundDetail]:
        records = await self._fund_repo.get_all()
        return [_fund_to_detail(r) for r in records]

    async def create_fund(
        self,
        *,
        slug: str,
        name: str,
        base_currency: str,
        actor: RequestContext,
    ) -> FundDetail:
        existing = await self._fund_repo.get_by_slug(slug)
        if existing is not None:
            raise ValidationError("Fund slug already in use")
        record = FundRecord(
            slug=slug, name=name,
            status=FundStatus.ACTIVE, base_currency=base_currency,
        )
        await self._fund_repo.insert(record)

        # Provision fund infrastructure (schema + Kafka topics)
        if self._engine is not None:
            from app.shared.fund_schema import create_fund_schema

            await create_fund_schema(self._engine, slug)

        if self._event_bus is not None:
            from app.shared.fund_schema import create_fund_kafka_topics
            from app.shared.schema_registry import fund_topic

            create_fund_kafka_topics(self._event_bus, slug)
            # Subscribe audit consumer for the new fund
            self._event_bus.subscribe(
                fund_topic(slug, "trades.executed"),
                self._audit.insert,
            )

        await self._audit.insert_admin_event(
            event_type="admin.fund.created",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=slug,
            payload={"fund_id": record.id, "slug": slug, "name": name},
        )
        return _fund_to_detail(record)

    async def update_fund(
        self,
        fund_id: str,
        *,
        actor: RequestContext,
        **fields: object,
    ) -> FundDetail:
        record = await self._fund_repo.update(fund_id, **fields)
        if record is None:
            raise NotFoundError("Fund", fund_id)
        await self._audit.insert_admin_event(
            event_type="admin.fund.updated",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=record.slug,
            payload={"fund_id": fund_id, "fields": {k: str(v) for k, v in fields.items()}},
        )
        return _fund_to_detail(record)

    # ----- Fund access grants -----

    async def list_fund_access(self, fund_id: str) -> list[FundAccessGrant]:
        """List all access grants on a fund via a single FGA read."""
        tuples = await self._fga.read_tuples(object=f"fund:{fund_id}")

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
            record = await self._user_repo.get_by_id(uid)
            if record:
                names[f"user:{uid}"] = record.name
        for oid in operator_ids:
            record = await self._operator_repo.get_by_id(oid)
            if record:
                names[f"operator:{oid}"] = record.name

        grants: list[FundAccessGrant] = []
        for fga_user, relation, _obj in tuples:
            if ":" not in fga_user:
                continue
            user_type, subject_id = fga_user.split(":", 1)
            if user_type not in ("user", "operator"):
                continue
            grants.append(FundAccessGrant(
                user_type=user_type,
                user_id=subject_id,
                relation=relation,
                display_name=names.get(fga_user),
            ))

        return grants

    async def grant_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        actor: RequestContext,
    ) -> None:
        """Grant a user or operator a relation on a fund via FGA."""
        fund = await self._fund_repo.get_by_id(fund_id)
        if fund is None:
            raise NotFoundError("Fund", fund_id)
        # Validate that the subject exists
        if user_type == "user" and await self._user_repo.get_by_id(user_id) is None:
            raise NotFoundError("User", user_id)
        elif user_type == "operator" and await self._operator_repo.get_by_id(user_id) is None:
            raise NotFoundError("Operator", user_id)
        await self._fga.write_tuples([
            ClientTuple(
                user=f"{user_type}:{user_id}",
                relation=relation,
                object=f"fund:{fund_id}",
            )
        ])
        # Invalidate auth cache so the change takes effect immediately
        if user_type == "user" and self._auth_service is not None:
            self._auth_service.invalidate_fga_cache(user_id, fund_id)

        await self._audit.insert_admin_event(
            event_type="admin.access.granted",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=fund.slug,
            payload={
                "fund_id": fund_id, "user_type": user_type,
                "user_id": user_id, "relation": relation,
            },
        )

    async def revoke_access(
        self,
        fund_id: str,
        *,
        user_type: str,
        user_id: str,
        relation: str,
        actor: RequestContext,
    ) -> None:
        """Revoke a user or operator's relation on a fund via FGA."""
        fund = await self._fund_repo.get_by_id(fund_id)
        if fund is None:
            raise NotFoundError("Fund", fund_id)
        await self._fga.delete_tuples([
            ClientTuple(
                user=f"{user_type}:{user_id}",
                relation=relation,
                object=f"fund:{fund_id}",
            )
        ])
        # Invalidate auth cache so the change takes effect immediately
        if user_type == "user" and self._auth_service is not None:
            self._auth_service.invalidate_fga_cache(user_id, fund_id)

        await self._audit.insert_admin_event(
            event_type="admin.access.revoked",
            actor_id=actor.actor_id,
            actor_type=actor.actor_type.value,
            fund_slug=fund.slug,
            payload={
                "fund_id": fund_id, "user_type": user_type,
                "user_id": user_id, "relation": relation,
            },
        )

    # ----- Audit -----

    async def list_audit(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditPage:
        records, total = await self._audit.query(
            fund_slug=fund_slug, event_type=event_type,
            limit=limit, offset=offset,
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


def _user_to_info(r: UserRecord) -> UserInfo:
    return UserInfo(id=r.id, email=r.email, name=r.name, is_active=r.is_active)


def _operator_to_info(
    r: OperatorRecord, *, platform_role: str | None = None
) -> OperatorInfo:
    return OperatorInfo(
        id=r.id, email=r.email, name=r.name,
        is_active=r.is_active, platform_role=platform_role,
    )


def _fund_to_detail(r: FundRecord) -> FundDetail:
    return FundDetail(
        id=r.id, slug=r.slug, name=r.name,
        status=r.status, base_currency=r.base_currency,
    )
