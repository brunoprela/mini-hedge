"""FX hedging repositories."""

from app.modules.fx_hedging.repositories.forward import FXForwardRepository
from app.modules.fx_hedging.repositories.interest_rate import FXInterestRateRepository

__all__ = [
    "FXForwardRepository",
    "FXInterestRateRepository",
]
