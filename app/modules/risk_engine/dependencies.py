"""FastAPI dependency wrappers for the risk engine module."""

from fastapi import HTTPException, Request

from app.modules.risk_engine.services import (
    CounterpartyRiskService,
    LiquidityMarginService,
    RiskSnapshotService,
)


def get_risk_snapshot_service(request: Request) -> RiskSnapshotService:
    service: RiskSnapshotService | None = getattr(request.app.state, "risk_snapshot_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="RiskSnapshotService not initialized",
        )
    return service


def get_counterparty_risk_service(request: Request) -> CounterpartyRiskService:
    service: CounterpartyRiskService | None = getattr(
        request.app.state, "counterparty_risk_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="CounterpartyRiskService not initialized",
        )
    return service


def get_liquidity_margin_service(request: Request) -> LiquidityMarginService:
    service: LiquidityMarginService | None = getattr(
        request.app.state, "liquidity_margin_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="LiquidityMarginService not initialized",
        )
    return service
