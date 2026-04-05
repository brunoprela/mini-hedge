"""Contract tests — validate API endpoints match their OpenAPI spec.

Uses ``schemathesis.openapi.from_asgi`` (v4 API) to load the schema
directly from the FastAPI ASGI app and auto-generate test cases for
every endpoint.

Run with:  uv run pytest tests/contract -m contract
"""

from __future__ import annotations

import pytest
import schemathesis

from app.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app=app)


@pytest.mark.contract
@schema.parametrize()
def test_api_contract(case):  # type: ignore[no-untyped-def]
    """Every endpoint must conform to its declared OpenAPI schema."""
    case.call_and_validate()
