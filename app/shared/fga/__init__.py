"""OpenFGA authorization subpackage.

Re-exports all public symbols from client, resources, and startup modules
so existing ``from app.shared.fga import ...`` imports continue to work.
"""

from app.shared.fga.client import (
    FGAClient,
    ParamSource,
    ResourceRelation,
    ResourceType,
    qualify_object_id,
    register_resource_type,
    require_access,
    validate_resource_registry,
)
from app.shared.fga.resources import Fund, Platform, Portfolio
from app.shared.fga.startup import MODEL_PATH, initialize_fga

__all__ = [
    # client
    "FGAClient",
    "qualify_object_id",
    "ParamSource",
    "ResourceRelation",
    "ResourceType",
    "register_resource_type",
    "require_access",
    "validate_resource_registry",
    # resources
    "Fund",
    "Platform",
    "Portfolio",
    # startup
    "MODEL_PATH",
    "initialize_fga",
]
