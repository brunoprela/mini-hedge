"""FX hedging public interface."""

from app.modules.fx_hedging.interfaces.contract import (
    FXForwardClose,
    FXForwardContract,
    FXForwardCreate,
    FXForwardDirection,
    FXForwardRoll,
    FXForwardStatus,
    FXInterestRate,
)
from app.modules.fx_hedging.interfaces.recommendation import (
    FXHedgingReader,
    FXHedgingSummary,
    HedgeRecommendationResponse,
    RollRecommendation,
)

__all__ = [
    "FXForwardClose",
    "FXForwardContract",
    "FXForwardCreate",
    "FXForwardDirection",
    "FXForwardRoll",
    "FXForwardStatus",
    "FXHedgingReader",
    "FXHedgingSummary",
    "FXInterestRate",
    "HedgeRecommendationResponse",
    "RollRecommendation",
]
