"""Regulatory models package."""

from app.modules.regulatory.models.investor_statement import InvestorStatementRecord
from app.modules.regulatory.models.performance_letter import PerformanceLetterRecord
from app.modules.regulatory.models.regulatory_filing import RegulatoryFilingRecord
from app.shared.models import Base as Base

__all__ = [
    "InvestorStatementRecord",
    "PerformanceLetterRecord",
    "RegulatoryFilingRecord",
]
