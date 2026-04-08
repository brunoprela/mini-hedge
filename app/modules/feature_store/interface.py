"""Feature store — public interface and DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict  # noqa: TC002

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FeatureType(StrEnum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    VECTOR = "vector"


class ComputeMethod(StrEnum):
    SQL = "sql"
    PYTHON = "python"
    DERIVED = "derived"


class FeatureStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class FeatureDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    description: str
    feature_type: FeatureType
    compute_method: ComputeMethod
    expression: str
    dependencies: list[str] = []
    entity_type: str  # "instrument", "portfolio", "fund"
    version: int
    status: FeatureStatus
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime


class FeatureValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature_name: str
    entity_id: str
    value: Any
    computed_at: datetime
    version: int


class FeatureVector(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    features: dict[str, Any]
    computed_at: datetime


class FeatureSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    description: str
    feature_names: list[str]
    entity_type: str
    created_at: datetime


class FeatureStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature_name: str
    count: int
    mean: Decimal | None
    std: Decimal | None
    min_val: Decimal | None
    max_val: Decimal | None
    null_count: int
    last_computed: datetime | None
