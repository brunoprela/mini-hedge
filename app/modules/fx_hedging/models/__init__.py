"""FX hedging models package."""

from app.modules.fx_hedging.models.fx_forward import FXForwardRecord
from app.modules.fx_hedging.models.fx_interest_rate import FXInterestRateRecord
from app.shared.models import Base as Base

__all__ = [
    "FXForwardRecord",
    "FXInterestRateRecord",
]
