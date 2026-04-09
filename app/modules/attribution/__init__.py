"""Attribution bounded context — Brinson-Fachler and risk-based performance attribution."""

from app.modules.attribution.interface import (
    AttributionMethod,
    AttributionReader,
    BrinsonFachlerResult,
    RiskBasedResult,
)
from app.modules.attribution.service import AttributionService

__all__ = [
    "AttributionMethod",
    "AttributionReader",
    "AttributionService",
    "BrinsonFachlerResult",
    "RiskBasedResult",
]
