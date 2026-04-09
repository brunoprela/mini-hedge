"""FastAPI dependency wrappers for investor operations."""

from fastapi import HTTPException, Request

from app.modules.investor_operations.services import (
    InvestorKYCService,
    RedemptionService,
    SubscriptionService,
)


def get_subscription_service(request: Request) -> SubscriptionService:
    service: SubscriptionService | None = getattr(request.app.state, "subscription_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Subscription service not initialized",
        )
    return service


def get_redemption_service(request: Request) -> RedemptionService:
    service: RedemptionService | None = getattr(request.app.state, "redemption_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Redemption service not initialized",
        )
    return service


def get_kyc_service(request: Request) -> InvestorKYCService:
    service: InvestorKYCService | None = getattr(request.app.state, "kyc_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="KYC service not initialized",
        )
    return service
