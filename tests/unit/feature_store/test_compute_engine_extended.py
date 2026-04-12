"""Extended unit tests for FeatureComputeEngine — SQL compute and edge cases."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.feature_store.core.compute_engine import (
    FeatureComputeEngine,
    _volatility,
)
from app.modules.feature_store.interfaces import (
    ComputeMethod,
    FeatureDefinition,
    FeatureStatus,
    FeatureType,
)


def _make_definition(
    expression: str,
    compute_method: ComputeMethod = ComputeMethod.PYTHON,
    name: str = "test_feature",
) -> FeatureDefinition:
    return FeatureDefinition(
        id=uuid4(),
        name=name,
        description="test",
        feature_type=FeatureType.NUMERIC,
        compute_method=compute_method,
        expression=expression,
        entity_type="instrument",
        version=1,
        status=FeatureStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestComputeMethodBranching:
    """Cover the compute method dispatch branches in compute()."""

    def test_sql_compute_method_delegates_to_compute_sql(self):
        engine = FeatureComputeEngine()
        defn = _make_definition(
            "SELECT 42 as result",
            compute_method=ComputeMethod.SQL,
        )
        # Patch _compute_sql to avoid real duckdb dependency
        with patch.object(engine, "_compute_sql", return_value=Decimal("42")) as mock_sql:
            result = engine.compute(defn, {"x": 1})
            mock_sql.assert_called_once_with("SELECT 42 as result", {"x": 1})
            assert result == Decimal("42")

    def test_unknown_compute_method_returns_none(self):
        engine = FeatureComputeEngine()
        defn = _make_definition("something", compute_method=ComputeMethod.PYTHON)
        # Manually override compute_method to something unrecognized
        # by making a new definition with an unknown method via a mock
        mock_defn = MagicMock()
        mock_defn.compute_method = "unknown_method"
        mock_defn.expression = "x"
        result = engine.compute(mock_defn, {})
        assert result is None


class TestComputeSQLMethod:
    """Test _compute_sql with mocked duckdb."""

    def test_sql_with_rows_data(self):
        engine = FeatureComputeEngine()
        # Mock duckdb and pyarrow
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (42.5,)

        with patch.dict("sys.modules", {"duckdb": MagicMock(), "pyarrow": MagicMock()}):
            with patch("duckdb.connect", return_value=mock_conn):
                # Import after patching
                result = FeatureComputeEngine._compute_sql(
                    "SELECT AVG(price) FROM input_data",
                    {"rows": [{"price": 10}, {"price": 20}]},
                )
        # Due to mocking complexities, let's test via the engine directly
        # with the real method but mock duckdb at import level

    def test_sql_duckdb_not_installed(self):
        """When duckdb is not importable, returns None."""
        engine = FeatureComputeEngine()
        # Temporarily hide duckdb
        import sys

        original = sys.modules.get("duckdb")
        sys.modules["duckdb"] = None  # type: ignore[assignment]
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT 1", {"x": 1}
            )
            assert result is None
        finally:
            if original is not None:
                sys.modules["duckdb"] = original
            else:
                sys.modules.pop("duckdb", None)

    def test_sql_with_single_row_data(self):
        """Test the single-row table creation path."""
        engine = FeatureComputeEngine()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (3.14,)

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        import sys

        original = sys.modules.get("duckdb")
        sys.modules["duckdb"] = mock_duckdb
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT price FROM input_data",
                {"price": "100", "volume": "500"},
            )
            # The single-row path should create a table and execute
            assert mock_conn.execute.called
            # Result is a float so should be converted to Decimal
            assert result == Decimal(str(round(3.14, 8)))
        finally:
            if original is not None:
                sys.modules["duckdb"] = original
            else:
                sys.modules.pop("duckdb", None)

    def test_sql_with_parallel_arrays(self):
        """Test the parallel-arrays table creation path."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (25.0,)

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_pa = MagicMock()
        mock_table = MagicMock()
        mock_pa.table.return_value = mock_table

        import sys

        orig_duckdb = sys.modules.get("duckdb")
        orig_pa = sys.modules.get("pyarrow")
        sys.modules["duckdb"] = mock_duckdb
        sys.modules["pyarrow"] = mock_pa
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT AVG(price) FROM input_data",
                {"price": [10, 20, 30], "volume": [100, 200, 300]},
            )
            # Should use pyarrow to create table
            mock_pa.table.assert_called_once()
            mock_conn.register.assert_called_once_with("input_data", mock_table)
            assert result == Decimal(str(round(25.0, 8)))
        finally:
            if orig_duckdb is not None:
                sys.modules["duckdb"] = orig_duckdb
            else:
                sys.modules.pop("duckdb", None)
            if orig_pa is not None:
                sys.modules["pyarrow"] = orig_pa
            else:
                sys.modules.pop("pyarrow", None)

    def test_sql_with_rows_data_path(self):
        """Test the rows data path."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (15.0,)

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_pa = MagicMock()
        mock_table = MagicMock()
        mock_pa.table.return_value = mock_table

        import sys

        orig_duckdb = sys.modules.get("duckdb")
        orig_pa = sys.modules.get("pyarrow")
        sys.modules["duckdb"] = mock_duckdb
        sys.modules["pyarrow"] = mock_pa
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT AVG(price) as result FROM input_data",
                {"rows": [{"price": 10}, {"price": 20}]},
            )
            mock_pa.table.assert_called_once()
            mock_conn.register.assert_called_once()
            assert result == Decimal(str(round(15.0, 8)))
        finally:
            if orig_duckdb is not None:
                sys.modules["duckdb"] = orig_duckdb
            else:
                sys.modules.pop("duckdb", None)
            if orig_pa is not None:
                sys.modules["pyarrow"] = orig_pa
            else:
                sys.modules.pop("pyarrow", None)

    def test_sql_empty_rows_returns_none(self):
        """Empty rows list returns None early."""
        mock_conn = MagicMock()

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_pa = MagicMock()

        import sys

        orig_duckdb = sys.modules.get("duckdb")
        orig_pa = sys.modules.get("pyarrow")
        sys.modules["duckdb"] = mock_duckdb
        sys.modules["pyarrow"] = mock_pa
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT 1 FROM input_data",
                {"rows": []},
            )
            assert result is None
        finally:
            if orig_duckdb is not None:
                sys.modules["duckdb"] = orig_duckdb
            else:
                sys.modules.pop("duckdb", None)
            if orig_pa is not None:
                sys.modules["pyarrow"] = orig_pa
            else:
                sys.modules.pop("pyarrow", None)

    def test_sql_fetchone_returns_none(self):
        """When query returns no rows, result is None."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        import sys

        orig = sys.modules.get("duckdb")
        sys.modules["duckdb"] = mock_duckdb
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT price FROM input_data WHERE 1=0",
                {"price": "100"},
            )
            assert result is None
        finally:
            if orig is not None:
                sys.modules["duckdb"] = orig
            else:
                sys.modules.pop("duckdb", None)

    def test_sql_non_float_result(self):
        """When result is not a float (e.g. string), return as-is."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("hello",)

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        import sys

        orig = sys.modules.get("duckdb")
        sys.modules["duckdb"] = mock_duckdb
        try:
            result = FeatureComputeEngine._compute_sql(
                "SELECT name FROM input_data",
                {"name": "hello"},
            )
            assert result == "hello"
        finally:
            if orig is not None:
                sys.modules["duckdb"] = orig
            else:
                sys.modules.pop("duckdb", None)

    def test_sql_exception_returns_none(self):
        """When duckdb execution fails, returns None."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("bad sql")

        mock_duckdb = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        import sys

        orig = sys.modules.get("duckdb")
        sys.modules["duckdb"] = mock_duckdb
        try:
            result = FeatureComputeEngine._compute_sql(
                "INVALID SQL",
                {"price": "100"},
            )
            assert result is None
        finally:
            if orig is not None:
                sys.modules["duckdb"] = orig
            else:
                sys.modules.pop("duckdb", None)


class TestVolatilityEdgeCases:
    def test_volatility_empty_recent_returns_zero(self):
        """All zero prices -> no valid daily returns -> empty recent -> 0.0."""
        # All zero prices means every i-1 price is 0, so all returns are skipped
        result = _volatility([0.0, 0.0, 0.0, 0.0], 5)
        assert result == 0.0


class TestComputePythonEdgeCases:
    def test_float_literal_arg(self):
        """Arg that is not in data and not an int but a float literal."""
        engine = FeatureComputeEngine()
        defn = _make_definition("pe_ratio(price, 10.5)")
        result = engine.compute(defn, {"price": 105.0})
        assert result == Decimal("10.0")
