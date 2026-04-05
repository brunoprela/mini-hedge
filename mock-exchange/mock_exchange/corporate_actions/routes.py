"""Corporate actions REST endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request

from mock_exchange.corporate_actions.models import CorporateAction

router = APIRouter(tags=["Corporate Actions"])


def _get_engine(request: Request):  # noqa: ANN202
    return request.app.state.corporate_actions_engine


@router.get("/corporate-actions", response_model=list[CorporateAction])
async def list_corporate_actions(
    request: Request,
    instrument_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[CorporateAction]:
    """List corporate actions with optional filters."""
    engine = _get_engine(request)
    return engine.get_all_actions(instrument_id=instrument_id, start=start, end=end)


@router.get("/corporate-actions/{action_id}", response_model=CorporateAction)
async def get_corporate_action(request: Request, action_id: str) -> CorporateAction:
    """Get a single corporate action by ID."""
    engine = _get_engine(request)
    action = engine.get_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Corporate action {action_id} not found")
    return action


@router.post("/corporate-actions/generate", response_model=list[CorporateAction])
async def generate_corporate_actions(
    request: Request,
    business_date: date | None = None,
) -> list[CorporateAction]:
    """Trigger generation of corporate actions for a business date.

    Defaults to today if no date is provided.
    """
    engine = _get_engine(request)
    target_date = business_date or date.today()
    return engine.generate_actions(target_date)
