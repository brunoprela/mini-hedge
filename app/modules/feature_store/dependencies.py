"""FastAPI dependency wrappers for the feature_store module."""


from fastapi import HTTPException, Request

from app.modules.feature_store.services import FeatureStoreService


def get_feature_store_service(request: Request) -> FeatureStoreService:
    service: FeatureStoreService | None = getattr(
        request.app.state,
        "feature_store_service",
        None,
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="FeatureStoreService not initialized",
        )
    return service
