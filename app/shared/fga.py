"""OpenFGA client wrapper and FastAPI dependencies for object-level authorization.

Provides:
- ResourceType / ResourceRelation: type-safe declarations linked to fga_model.json
- FGAClient: thin wrapper around the OpenFGA SDK async client
- initialize_fga(): store + model setup (idempotent, called from lifespan)
- require_access(): generic FastAPI dependency for any resource type
- validate_resource_registry(): startup check that Python types match JSON model
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, HTTPException, Request
from openfga_sdk import (
    ClientConfiguration,
    CreateStoreRequest,
    OpenFgaClient,
    WriteAuthorizationModelRequest,
)
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientTuple,
    ClientWriteRequest,
    ClientWriteRequestOnDuplicateWrites,
    ConflictOptions,
)

from app.shared.auth import get_actor_context

if TYPE_CHECKING:
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()

# Path to the canonical authorization model (version-controlled JSON).
MODEL_PATH = Path(__file__).resolve().parent.parent / "modules" / "platform" / "fga_model.json"


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

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# ---------------------------------------------------------------------------
# Authorization model — loaded from JSON file
# ---------------------------------------------------------------------------


def _load_model_json() -> dict:
    """Load the authorization model from the version-controlled JSON file."""
    return json.loads(MODEL_PATH.read_text())


def _model_hash(model_json: dict) -> str:
    """Stable hash of the model for change detection."""
    canonical = json.dumps(model_json, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


async def _get_latest_model_types(client: OpenFgaClient) -> list[dict] | None:
    """Read the latest authorization model's type_definitions, or None if none exists."""
    response = await client.read_latest_authorization_model()
    model = getattr(response, "authorization_model", None)
    if model is None:
        return None
    return [td.to_dict() for td in (model.type_definitions or [])]


def _normalize(obj: object) -> object:
    """Strip None values recursively so two models compare equal regardless of SDK nulls."""
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_normalize(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Initialization (called from lifespan)
# ---------------------------------------------------------------------------


async def _find_or_create_store(client: OpenFgaClient, store_name: str) -> str:
    """Find an existing store by name, or create one."""
    stores_response = await client.list_stores()
    for store in stores_response.stores or []:
        if store.name == store_name:
            return store.id

    create_response = await client.create_store(
        body=CreateStoreRequest(name=store_name),
    )
    return create_response.id


async def initialize_fga(*, api_url: str, store_name: str) -> FGAClient:
    """Create store (if needed), write authorization model only if changed.

    Compares the local JSON model against the latest model in the store.
    Skips the write if they match, avoiding duplicate versions on every restart.
    """
    # Bootstrap client without store_id to list/create stores
    bootstrap_config = ClientConfiguration(api_url=api_url)
    bootstrap_client = OpenFgaClient(bootstrap_config)

    store_id = await _find_or_create_store(bootstrap_client, store_name)
    await bootstrap_client.close()

    # Client with store_id to read/write model
    store_config = ClientConfiguration(api_url=api_url, store_id=store_id)
    store_client = OpenFgaClient(store_config)

    # Load local model from JSON file
    model_json = _load_model_json()
    local_types = _normalize(model_json.get("type_definitions", []))

    # Compare with latest model in store
    remote_types = await _get_latest_model_types(store_client)
    remote_types_normalized = _normalize(remote_types) if remote_types else None

    if remote_types_normalized == local_types:
        response = await store_client.read_latest_authorization_model()
        model_id = response.authorization_model.id
        logger.info("fga_model_unchanged", store_id=store_id, model_id=model_id)
    else:
        model_request = WriteAuthorizationModelRequest(**model_json)
        model_response = await store_client.write_authorization_model(body=model_request)
        model_id = model_response.authorization_model_id
        local_hash = _model_hash(model_json)
        logger.info("fga_model_written", store_id=store_id, model_id=model_id, hash=local_hash)

    await store_client.close()

    # Validate Python resource declarations match the JSON model
    validate_resource_registry(model_json)

    # Final client pinned to store + model
    final_config = ClientConfiguration(
        api_url=api_url,
        store_id=store_id,
        authorization_model_id=model_id,
    )
    final_client = OpenFgaClient(final_config)

    logger.info("fga_initialized", store_id=store_id, model_id=model_id)
    return FGAClient(final_client)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


class ParamSource(StrEnum):
    """Where to extract the resource ID from the request."""

    PATH = "path"
    BODY = "body"
    QUERY = "query"


def _get_fga(request: Request) -> FGAClient | None:
    """Extract the FGA client from app state, or None if FGA is disabled."""
    return getattr(request.app.state, "fga", None)


async def _extract_resource_id(
    request: Request,
    param_name: str,
    source: ParamSource,
) -> str:
    """Pull the resource ID from the request path, body, or query."""
    if source == ParamSource.PATH:
        value = request.path_params.get(param_name)
    elif source == ParamSource.BODY:
        body = await request.json()
        value = body.get(param_name)
    elif source == ParamSource.QUERY:
        value = request.query_params.get(param_name)
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
        resource_id = await _extract_resource_id(request, param_name, source)
        allowed = await fga.check(
            user=f"user:{ctx.actor_id}",
            relation=resource_relation.relation,
            object=f"{rt.name}:{resource_id}",
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"No {resource_relation.relation} access to {rt.name} {resource_id}",
            )

    return Depends(_check)
