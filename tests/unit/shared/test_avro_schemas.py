"""Unit tests for Avro schema files — verify all .avsc files parse correctly."""

from __future__ import annotations

import json
from pathlib import Path

import fastavro
import pytest

SCHEMA_DIR = Path("schemas")


def _find_all_avsc() -> list[Path]:
    """Discover all .avsc files under the schemas directory."""
    return sorted(SCHEMA_DIR.rglob("*.avsc"))


@pytest.fixture(params=_find_all_avsc(), ids=lambda p: str(p.relative_to(SCHEMA_DIR)))
def avsc_path(request) -> Path:
    return request.param


class TestAvroSchemas:
    def test_all_schemas_discovered(self) -> None:
        schemas = _find_all_avsc()
        # 12 original + 9 new = 21 total
        assert len(schemas) >= 21

    def test_schema_is_valid_json(self, avsc_path: Path) -> None:
        with avsc_path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "type" in data

    def test_schema_parses_as_avro(self, avsc_path: Path) -> None:
        with avsc_path.open() as f:
            schema = json.load(f)
        # fastavro.parse_schema raises if the schema is invalid
        parsed = fastavro.parse_schema(schema)
        assert parsed is not None

    def test_schema_has_name_and_namespace(self, avsc_path: Path) -> None:
        with avsc_path.open() as f:
            schema = json.load(f)
        assert "name" in schema
        assert "namespace" in schema

    def test_schema_has_fields(self, avsc_path: Path) -> None:
        with avsc_path.open() as f:
            schema = json.load(f)
        if schema.get("type") == "record":
            assert "fields" in schema
            assert len(schema["fields"]) > 0


class TestNewSchemas:
    """Verify the 9 new schemas exist and have expected names."""

    @pytest.mark.parametrize(
        "path,expected_name",
        [
            ("market-data/status-v1.avsc", "MarketDataStatus"),
            ("corporate-actions/announced-v1.avsc", "CorporateActionAnnounced"),
            ("orders/intents-generated-v1.avsc", "OrderIntentGenerated"),
            ("orders/canceled-v1.avsc", "OrderCanceled"),
            ("attribution/calculated-v1.avsc", "AttributionCalculated"),
            ("cash/projected-v1.avsc", "CashProjected"),
            ("cash/balance-warning-v1.avsc", "CashBalanceWarning"),
            ("eod/lifecycle-v1.avsc", "EODLifecycle"),
            ("users/role-changed-v1.avsc", "UserRoleChanged"),
        ],
    )
    def test_new_schema_exists_and_named(self, path: str, expected_name: str) -> None:
        schema_path = SCHEMA_DIR / path
        assert schema_path.exists(), f"Missing schema: {path}"
        with schema_path.open() as f:
            schema = json.load(f)
        assert schema["name"] == expected_name
