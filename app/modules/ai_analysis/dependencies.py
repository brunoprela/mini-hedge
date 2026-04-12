"""FastAPI dependency wrappers for the AI analysis module."""


from fastapi import HTTPException, Request

from app.modules.ai_analysis.services import AIAnalysisService


def get_ai_analysis_service(request: Request) -> AIAnalysisService:
    service: AIAnalysisService | None = getattr(request.app.state, "ai_analysis_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="AIAnalysisService not initialized",
        )
    return service
