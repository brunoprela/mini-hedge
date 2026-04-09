"""Quant research bounded context — factor analysis and regime detection."""

from app.modules.quant_research.interface import (
    FactorAnalysisResult,
    FactorType,
    MarketRegime,
    RegimeAnalysis,
    RegimeType,
)
from app.modules.quant_research.service import QuantResearchService

__all__ = [
    "FactorAnalysisResult",
    "FactorType",
    "MarketRegime",
    "QuantResearchService",
    "RegimeAnalysis",
    "RegimeType",
]
