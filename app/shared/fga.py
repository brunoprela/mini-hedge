"""OpenFGA client wrapper and FastAPI dependencies for object-level authorization.

Provides:
- ResourceType / ResourceRelation: type-safe declarations linked to fga_model.json
- FGAClient: thin wrapper around the OpenFGA SDK async client
- require_access(): generic FastAPI dependency for any resource type
- validate_resource_registry(): startup check that Python types match JSON model
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, HTTPException, Request
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientListObjectsRequest,
    ClientListRelationsRequest,
    ClientTuple,
    ClientWriteRequest,
    ClientWriteRequestOnDuplicateWrites,
    ConflictOptions,
)

from app.shared.auth import get_actor_context

if TYPE_CHECKING:
    from openfga_sdk import OpenFgaClient

    from app.shared.request_context import RequestContext

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Resource type registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceType:
    """Declaration of an FGA object type and its checkable relations.

    Each instance maps to a ``type_definition`` in ``fga_model.json``.
    Validated at startup by :func:`validate_resource_registry`.
    """

    name: str
    relations: frozenset[str]

    def relation(self, name: str) -> ResourceRelation:
        """Return a validated (type, relation) pair for use with :func:`require_access`."""
        if name not in self.relations:
            raise ValueError(
                f"Unknown relation '{name}' for type '{self.name}'. Valid: {sorted(self.relations)}"
            )
        return ResourceRelation(resource_type=self, relation=name)


@dataclass(frozen=True)
class ResourceRelation:
    """A bound (resource_type, relation) pair passed to :func:`require_access`."""

    resource_type: ResourceType
    relation: str


_resource_registry: dict[str, ResourceType] = {}


def register_resource_type(rt: ResourceType) -> ResourceType:
    """Register a resource type. Returns it for assignment convenience."""
    _resource_registry[rt.name] = rt
    return rt


def validate_resource_registry(model_json: dict) -> None:
    """Validate that all registered ResourceTypes match the FGA model JSON.

    Call during app startup after loading the model. Raises ``ValueError``
    with a clear message if any Python-declared type or relation is missing
    from the JSON model.
    """
    json_types: dict[str, set[str]] = {}
    for td in model_json.get("type_definitions", []):
        type_name = td["type"]
        relations = set(td.get("relations", {}).keys())
        json_types[type_name] = relations

    errors: list[str] = []
    for rt_name, rt in _resource_registry.items():
        if rt_name not in json_types:
            errors.append(f"ResourceType '{rt_name}' not found in FGA model JSON")
            continue
        missing = rt.relations - json_types[rt_name]
        if missing:
            errors.append(
                f"ResourceType '{rt_name}' declares relations {sorted(missing)} "
                f"not in FGA model (model has: {sorted(json_types[rt_name])})"
            )

    if errors:
        raise ValueError(
            "FGA resource registry does not match model JSON:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


# ---------------------------------------------------------------------------
# FGA client wrapper
# ---------------------------------------------------------------------------


class FGAClient:
    """Thin async wrapper around the OpenFGA SDK client."""

    def __init__(self, client: OpenFgaClient) -> None:
        self._client = client

    async def check(self, *, user: str, relation: str, object: str) -> bool:
        """Check if *user* has *relation* on *object*."""
        response = await self._client.check(
            body=ClientCheckRequest(user=user, relation=relation, object=object),
        )
        return bool(response.allowed)

    async def write_tuples(self, tuples: list[ClientTuple]) -> None:
        """Write relationship tuples (ignores duplicates)."""
        await self._client.write(
            body=ClientWriteRequest(writes=tuples),
            options={
                "conflict": ConflictOptions(
                    on_duplicate_writes=ClientWriteRequestOnDuplicateWrites.IGNORE,
                ),
            },
        )

    async def delete_tuples(self, tuples: list[ClientTuple]) -> None:
        """Delete relationship tuples."""
        await self._client.write(
            body=ClientWriteRequest(deletes=tuples),
        )

    async def list_objects(self, *, user: str, relation: str, type: str) -> list[str]:
        """List object IDs where *user* has *relation* on objects of *type*."""
        response = await self._client.list_objects(
            body=ClientListObjectsRequest(user=user, relation=relation, type=type),
        )
        # Response objects are formatted as "type:id" — strip the prefix.
        prefix = f"{type}:"
        return [
            obj[len(prefix) :] if obj.startswith(prefix) else obj
            for obj in (response.objects or [])
        ]

    async def list_relations(self, *, user: str, object: str, relations: list[str]) -> list[str]:
        """Return which of *relations* the *user* has on *object*."""
        return await self._client.list_relations(
            body=ClientListRelationsRequest(user=user, object=object, relations=relations),
        )

    async def read_tuples(self, *, object: str) -> list[tuple[str, str, str]]:
        """Read all relationship tuples on *object*.

        Returns a list of ``(user, relation, object)`` triples.
        """
        from openfga_sdk import ReadRequestTupleKey

        response = await self._client.read(
            body=ReadRequestTupleKey(object=object),
        )
        return [(t.key.user, t.key.relation, t.key.object) for t in (response.tuples or [])]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


class ParamSource(StrEnum):
    """Where to extract the resource ID from the request."""

    PATH = "path"
    BODY = "body"
    QUERY = "query"
    CONTEXT = "context"


def _get_fga(request: Request) -> FGAClient | None:
    """Extract the FGA client from app state, or None if FGA is disabled."""
    return getattr(request.app.state, "fga", None)


async def _extract_resource_id(
    request: Request,
    param_name: str,
    source: ParamSource,
    ctx: RequestContext | None = None,
) -> str:
    """Pull the resource ID from the request path, body, query, or context."""
    if source == ParamSource.PATH:
        value = request.path_params.get(param_name)
    elif source == ParamSource.BODY:
        body = await request.json()
        value = body.get(param_name)
    elif source == ParamSource.QUERY:
        value = request.query_params.get(param_name)
    elif source == ParamSource.CONTEXT:
        if ctx is None:
            raise HTTPException(status_code=500, detail="Context not available for FGA check")
        value = getattr(ctx, param_name, None)
    else:
        raise ValueError(f"Unknown source: {source}")

    if value is None:
        raise HTTPException(
            status_code=400,
            detail=f"Missing {source.value} parameter: {param_name}",
        )
    return str(value)


def require_access(  # type: ignore[no-untyped-def]
    resource_relation: ResourceRelation,
    *,
    param: str | None = None,
    source: ParamSource = ParamSource.PATH,
):
    """Generic FastAPI dependency for FGA object-level access checks.

    Args:
        resource_relation: A bound (type, relation) pair from
            ``SomeResource.relation("can_view")``.
        param: Name of the parameter holding the resource ID.
            Defaults to ``"{type_name}_id"`` (e.g. ``"portfolio_id"``).
        source: Where to find the param — path, body, or query.

    Example::

        @router.get("/{portfolio_id}/positions")
        async def list_positions(
            portfolio_id: UUID,
            ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
            _access: None = require_access(Portfolio.relation("can_view")),
        ):
            ...
    """
    param_name = param or f"{resource_relation.resource_type.name}_id"
    rt = resource_relation.resource_type

    async def _check(
        request: Request,
        ctx: RequestContext = Depends(get_actor_context),
        fga: FGAClient | None = Depends(_get_fga),
    ) -> None:
        if fga is None:
            # FGA not enabled — skip object-level check (RBAC still enforced)
            return
        resource_id = await _extract_resource_id(request, param_name, source, ctx)
        # Use the correct FGA subject type based on actor type
        from app.shared.request_context import ActorType  # noqa: F811

        fga_prefix = "operator" if ctx.actor_type == ActorType.OPERATOR else "user"
        allowed = await fga.check(
            user=f"{fga_prefix}:{ctx.actor_id}",
            relation=resource_relation.relation,
            object=f"{rt.name}:{resource_id}",
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"No {resource_relation.relation} access to {rt.name} {resource_id}",
            )

    return Depends(_check)
