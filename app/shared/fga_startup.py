"""OpenFGA store and authorization model initialization.

Extracted from ``fga.py`` to separate startup/bootstrap logic from the
runtime client and FastAPI dependencies.

Called once during application lifespan to create/find the FGA store,
write the authorization model if changed, and return a configured
:class:`FGAClient`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import structlog
from openfga_sdk import (
    ClientConfiguration,
    CreateStoreRequest,
    OpenFgaClient,
    WriteAuthorizationModelRequest,
)

from app.shared.fga import FGAClient, validate_resource_registry

logger = structlog.get_logger()

# Path to the canonical authorization model (version-controlled JSON).
MODEL_PATH = Path(__file__).resolve().parent.parent / "modules" / "platform" / "fga_model.json"


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
