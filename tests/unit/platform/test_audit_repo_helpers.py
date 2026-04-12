"""Unit tests for audit repository pure functions — _compute_hash, _safe_payload."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.modules.platform.repositories.audit import _compute_hash, _safe_payload


class TestComputeHash:
    def test_produces_sha256_hex(self) -> None:
        result = _compute_hash("payload", "prev_hash")
        expected = hashlib.sha256(("payload" + "prev_hash").encode()).hexdigest()
        assert result == expected

    def test_empty_prev_hash(self) -> None:
        result = _compute_hash("data", "")
        expected = hashlib.sha256("data".encode()).hexdigest()
        assert result == expected

    def test_deterministic(self) -> None:
        h1 = _compute_hash("abc", "def")
        h2 = _compute_hash("abc", "def")
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        h1 = _compute_hash("abc", "def")
        h2 = _compute_hash("abc", "ghi")
        assert h1 != h2


class TestSafePayload:
    def test_extracts_event_fields(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = MagicMock()
        event.data = {"order_id": "o-1", "amount": 100}
        event.event_version = 1
        event.timestamp = now

        result = _safe_payload(event)

        assert result["data"] == {"order_id": "o-1", "amount": 100}
        assert result["event_version"] == 1
        assert result["timestamp"] == now.isoformat()

    def test_empty_data(self) -> None:
        event = MagicMock()
        event.data = {}
        event.event_version = 1
        event.timestamp = datetime(2024, 6, 1, tzinfo=timezone.utc)

        result = _safe_payload(event)

        assert result["data"] == {}
