"""Export FastAPI's OpenAPI schema to a JSON file without starting the server.

Usage:
    uv run python packages/api-types/scripts/export_schema.py
"""

import json
import sys
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from app.main import app

schema = get_openapi(
    title=app.title,
    version=app.version,
    routes=app.routes,
)

out = Path(__file__).resolve().parent.parent / "generated" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(schema, indent=2))
print(f"OpenAPI schema exported to {out} ({len(schema.get('components', {}).get('schemas', {}))} schemas)")
