"""FastAPI dependency wrappers for the quant research module."""


from fastapi import HTTPException, Request

from app.modules.quant_research.services import QuantResearchService


def get_quant_research_service(request: Request) -> QuantResearchService:
    service: QuantResearchService | None = getattr(
        request.app.state, "quant_research_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="QuantResearchService not initialized",
        )
    return service
