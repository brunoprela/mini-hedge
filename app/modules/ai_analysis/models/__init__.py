"""AI analysis models package."""

from app.modules.ai_analysis.models.analysis_result import AnalysisResultRecord
from app.modules.ai_analysis.models.research_note import ResearchNoteRecord
from app.shared.models import Base as Base

__all__ = [
    "AnalysisResultRecord",
    "ResearchNoteRecord",
]
