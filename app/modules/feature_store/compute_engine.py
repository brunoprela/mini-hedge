"""Feature computation engine — evaluates feature definitions against input data.

Expressions follow the format ``function_name(arg1, arg2, ...)`` where
arguments are either data keys (resolved at runtime) or literal numbers.
Nested expressions are not supported — compose features using the
``DERIVED`` compute method with dependency resolution instead.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import structlog

from app.modules.feature_store.interface import ComputeMethod, FeatureDefinition

logger = structlog.get_logger()


def _sma(prices: list[float], window: int) -> float:
    """Simple moving average over the last *window* prices."""
    if not prices or window <= 0:
        return 0.0
    subset = prices[-window:]
    return sum(subset) / len(subset)


def _ema(prices: list[float], window: int) -> float:
    """Exponential moving average."""
    if not prices or window <= 0:
        return 0.0
    alpha = 2.0 / (window + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = alpha * p + (1 - alpha) * ema
    return ema


def _rsi(prices: list[float], window: int) -> float:
    """Relative strength index (0-100)."""
    if len(prices) < 2 or window <= 0:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-window:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / window if gains else 0.0
    avg_loss = sum(losses) / window if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _bbands_width(prices: list[float], window: int) -> float:
    """Bollinger band width (upper - lower) / middle."""
    if len(prices) < window or window <= 0:
        return 0.0
    subset = prices[-window:]
    mean = sum(subset) / len(subset)
    if mean == 0:
        return 0.0
    variance = sum((p - mean) ** 2 for p in subset) / len(subset)
    std = math.sqrt(variance)
    return (4 * std) / mean  # width = 2*std above + 2*std below


def _returns(prices: list[float], window: int) -> float:
    """N-day return."""
    if len(prices) < window + 1 or window <= 0:
        return 0.0
    old = prices[-(window + 1)]
    if old == 0:
        return 0.0
    return (prices[-1] - old) / old


def _volatility(prices: list[float], window: int) -> float:
    """Rolling volatility (annualised) over *window* daily returns."""
    if len(prices) < 2 or window <= 0:
        return 0.0
    daily = [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] != 0
    ]
    recent = daily[-window:]
    if not recent:
        return 0.0
    mean = sum(recent) / len(recent)
    variance = sum((r - mean) ** 2 for r in recent) / len(recent)
    return math.sqrt(variance) * math.sqrt(252)


def _log_market_cap(market_cap: float) -> float:
    if market_cap <= 0:
        return 0.0
    return math.log(market_cap)


def _pe_ratio(price: float, earnings: float) -> float:
    if earnings == 0:
        return 0.0
    return price / earnings


def _book_to_market(book_value: float, market_cap: float) -> float:
    if market_cap == 0:
        return 0.0
    return book_value / market_cap


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

BUILTIN_FUNCTIONS: dict[str, Callable[..., float]] = {
    "sma": _sma,
    "ema": _ema,
    "rsi": _rsi,
    "bbands_width": _bbands_width,
    "returns": _returns,
    "volatility": _volatility,
    "log_market_cap": _log_market_cap,
    "pe_ratio": _pe_ratio,
    "book_to_market": _book_to_market,
}


class FeatureComputeEngine:
    """Computes feature values from definitions."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = data_dir

    def compute(
        self,
        definition: FeatureDefinition,
        data: dict[str, Any],
    ) -> Any:
        """Compute a single feature value from input data."""
        if definition.compute_method == ComputeMethod.PYTHON:
            return self._compute_python(definition.expression, data)
        if definition.compute_method == ComputeMethod.SQL:
            return self._compute_sql(definition.expression, data)
        if definition.compute_method == ComputeMethod.DERIVED:
            return self._compute_python(definition.expression, data)
        return None

    def compute_batch(
        self,
        definitions: list[FeatureDefinition],
        entities_data: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Compute multiple features for multiple entities.

        Returns ``{entity_id: {feature_name: value}}``.
        """
        results: dict[str, dict[str, Any]] = {}
        for entity_id, data in entities_data.items():
            entity_results: dict[str, Any] = {}
            for defn in definitions:
                entity_results[defn.name] = self.compute(defn, data)
            results[entity_id] = entity_results
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_sql(expression: str, data: dict[str, Any]) -> Any:
        """Execute SQL expression against in-memory data using DuckDB.

        The data dict is registered as a table named ``input_data``.
        Example: ``SELECT AVG(price) as result FROM input_data WHERE date > '2024-01-01'``
        """
        try:
            import duckdb
        except ImportError:
            logger.warning("duckdb_not_installed", msg="SQL features require duckdb")
            return None

        conn = duckdb.connect(":memory:")
        try:
            if "rows" in data:
                # data["rows"] is a list of dicts — register as table
                import pyarrow as pa

                if not data["rows"]:
                    return None
                columns = list(data["rows"][0].keys())
                arrays = {col: [row.get(col) for row in data["rows"]] for col in columns}
                table = pa.table(arrays)
                conn.register("input_data", table)
            elif any(isinstance(v, list) for v in data.values()):
                # Create table from parallel arrays
                import pyarrow as pa

                arrays = {k: v for k, v in data.items() if isinstance(v, list)}
                table = pa.table(arrays)
                conn.register("input_data", table)
            else:
                # Single-row data — create a one-row table
                columns = list(data.keys())
                values = list(data.values())
                col_defs = ", ".join(f'"{c}" VARCHAR' for c in columns)
                conn.execute(f"CREATE TABLE input_data ({col_defs})")
                placeholders = ", ".join("?" for _ in values)
                col_names = ", ".join(f'"{c}"' for c in columns)
                conn.execute(
                    f"INSERT INTO input_data ({col_names}) VALUES ({placeholders})",
                    [str(v) for v in values],
                )

            result = conn.execute(expression).fetchone()
            if result and len(result) > 0:
                val = result[0]
                if isinstance(val, float):
                    return Decimal(str(round(val, 8)))
                return val
            return None
        except Exception:
            logger.exception("duckdb_sql_error", expression=expression)
            return None
        finally:
            conn.close()

    @staticmethod
    def _compute_python(expression: str, data: dict[str, Any]) -> Any:
        """Evaluate a Python expression against built-in functions and data.

        The *expression* should be a function call like ``sma(prices, 20)``
        where ``prices`` is expected in *data*.
        """
        parts = expression.strip().split("(", 1)
        func_name = parts[0].strip()
        fn = BUILTIN_FUNCTIONS.get(func_name)
        if fn is None:
            logger.warning("unknown_feature_function", function=func_name)
            return None

        if len(parts) < 2:
            logger.warning("malformed_feature_expression", expression=expression)
            return None

        arg_str = parts[1].rstrip(") ")
        arg_names = [a.strip() for a in arg_str.split(",") if a.strip()]

        args: list[Any] = []
        for name in arg_names:
            # Resolve from data dict first, then try as literal number
            if name in data:
                val = data[name]
                # Convert Decimal lists to float lists for math functions
                if isinstance(val, list) and val and isinstance(val[0], Decimal):
                    args.append([float(v) for v in val])
                elif isinstance(val, Decimal):
                    args.append(float(val))
                else:
                    args.append(val)
            else:
                try:
                    args.append(int(name))
                except ValueError:
                    try:
                        args.append(float(name))
                    except ValueError:
                        logger.warning(
                            "unresolved_feature_arg",
                            arg=name,
                            expression=expression,
                        )
                        args.append(name)

        try:
            result = fn(*args)
            if isinstance(result, float):
                return Decimal(str(round(result, 8)))
            return result
        except Exception:
            logger.exception(
                "feature_compute_error",
                function=func_name,
                expression=expression,
            )
            return None
