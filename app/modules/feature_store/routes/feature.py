"""FastAPI routes for the feature store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.modules.feature_store.dependencies import get_feature_store_service
from app.modules.feature_store.interfaces import (
    ComputeMethod,
    FeatureDefinition,
    FeatureSet,
    FeatureStats,
    FeatureStatus,
    FeatureType,
    FeatureVector,
)
from app.modules.feature_store.services import FeatureStoreService
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/feature-store", tags=["feature-store"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RegisterFeatureRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    feature_type: FeatureType
    compute_method: ComputeMethod
    expression: str
    entity_type: str
    dependencies: list[str] = []
    tags: list[str] = []


class ComputeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature_names: list[str]
    entities_data: dict[str, dict[str, Any]]


class CreateFeatureSetRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    feature_names: list[str]
    entity_type: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/features", response_model=FeatureDefinition)
async def register_feature(
    body: RegisterFeatureRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_db),
) -> FeatureDefinition:
    return await service.register_feature(
        name=body.name,
        description=body.description,
        feature_type=body.feature_type,
        compute_method=body.compute_method,
        expression=body.expression,
        entity_type=body.entity_type,
        dependencies=body.dependencies,
        tags=body.tags,
        session=session,
    )


@router.get("/features", response_model=list[FeatureDefinition])
async def list_features(
    entity_type: str | None = Query(default=None),
    status: FeatureStatus | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FeatureDefinition]:
    return await service.list_features(
        entity_type=entity_type,
        status=status,
        session=session,
    )


@router.get("/features/{feature_name}", response_model=FeatureDefinition)
async def get_feature(
    feature_name: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_read_db),
) -> FeatureDefinition:
    record = await service._repo.get_by_name(feature_name, session=session)
    if record is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return FeatureStoreService._def_to_dto(record)


@router.get("/features/{feature_name}/stats", response_model=FeatureStats)
async def get_feature_stats(
    feature_name: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_read_db),
) -> FeatureStats:
    return await service.get_feature_stats(feature_name, session=session)


@router.post("/compute")
async def compute_features(
    body: ComputeRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, FeatureVector]:
    return await service.compute_features_batch(
        body.feature_names,
        body.entities_data,
        session=session,
    )


@router.get("/vectors/{entity_id}", response_model=FeatureVector)
async def get_feature_vector(
    entity_id: str,
    feature_names: list[str] = Query(...),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_read_db),
) -> FeatureVector:
    return await service.get_feature_vector(
        entity_id,
        feature_names,
        session=session,
    )


@router.post("/feature-sets", response_model=FeatureSet)
async def create_feature_set(
    body: CreateFeatureSetRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_db),
) -> FeatureSet:
    return await service.create_feature_set(
        name=body.name,
        description=body.description,
        feature_names=body.feature_names,
        entity_type=body.entity_type,
        session=session,
    )


@router.get("/feature-sets", response_model=list[FeatureSet])
async def list_feature_sets(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: FeatureStoreService = Depends(get_feature_store_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FeatureSet]:
    return await service.list_feature_sets(session=session)
