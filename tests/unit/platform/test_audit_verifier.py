"""Unit tests for AuditIntegrityVerifier — hash chain verification."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.platform.core.audit_verifier import AuditIntegrityVerifier, AuditVerificationResult
from app.modules.platform.repositories import _compute_hash


def _make_chain(payloads: list[dict]) -> list[MagicMock]:
    """Build a valid hash chain of mock AuditLogRecords."""
    records: list[MagicMock] = []
    prev_hash = ""
    for i, payload in enumerate(payloads):
        r = MagicMock()
        r.event_id = f"evt-{i}"
        r.payload = payload
        payload_str = json.dumps(payload, sort_keys=True)
        r.entry_hash = _compute_hash(payload_str, prev_hash)
        r.prev_hash = prev_hash or None
        r.created_at = i  # order key
        prev_hash = r.entry_hash
        records.append(r)
    return records


def _mock_session_context(records: list):
    """Create a mock async context manager for BaseRepository._session."""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = records
    session.execute = AsyncMock(return_value=result)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestComputeHash:
    def test_deterministic(self) -> None:
        h1 = _compute_hash("payload", "prev")
        h2 = _compute_hash("payload", "prev")
        assert h1 == h2

    def test_different_inputs(self) -> None:
        h1 = _compute_hash("a", "b")
        h2 = _compute_hash("c", "d")
        assert h1 != h2

    def test_empty_prev(self) -> None:
        h = _compute_hash("payload", "")
        assert isinstance(h, str) and len(h) == 64  # SHA-256 hex


class TestAuditVerificationResult:
    def test_valid_result(self) -> None:
        r = AuditVerificationResult(is_valid=True, records_checked=10)
        assert r.is_valid
        assert r.first_broken_link is None

    def test_invalid_result(self) -> None:
        r = AuditVerificationResult(is_valid=False, records_checked=5, first_broken_link="evt-4")
        assert not r.is_valid
        assert r.first_broken_link == "evt-4"


class TestAuditIntegrityVerifier:
    @pytest.mark.asyncio
    async def test_empty_chain_is_valid(self) -> None:
        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context([]))

        result = await verifier.verify()

        assert result.is_valid
        assert result.records_checked == 0

    @pytest.mark.asyncio
    async def test_valid_chain(self) -> None:
        records = _make_chain([
            {"action": "create_user", "user_id": "u-1"},
            {"action": "update_user", "user_id": "u-1"},
            {"action": "delete_user", "user_id": "u-1"},
        ])
        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert result.is_valid
        assert result.records_checked == 3

    @pytest.mark.asyncio
    async def test_broken_entry_hash(self) -> None:
        records = _make_chain([
            {"action": "a"},
            {"action": "b"},
            {"action": "c"},
        ])
        # Tamper with record 1's entry_hash
        records[1].entry_hash = "tampered_hash_value"

        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert not result.is_valid
        assert result.first_broken_link == "evt-1"
        assert result.records_checked == 2

    @pytest.mark.asyncio
    async def test_broken_prev_hash(self) -> None:
        records = _make_chain([
            {"action": "a"},
            {"action": "b"},
        ])
        # Tamper with record 1's prev_hash (but leave entry_hash valid)
        records[1].prev_hash = "wrong_prev_hash"

        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert not result.is_valid
        assert result.first_broken_link == "evt-1"

    @pytest.mark.asyncio
    async def test_first_record_wrong_prev_hash(self) -> None:
        records = _make_chain([{"action": "a"}])
        # First record's prev_hash should be None; set to something else
        records[0].prev_hash = "should_be_none"

        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert not result.is_valid
        assert result.first_broken_link == "evt-0"

    @pytest.mark.asyncio
    async def test_single_valid_record(self) -> None:
        records = _make_chain([{"action": "init"}])

        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert result.is_valid
        assert result.records_checked == 1

    @pytest.mark.asyncio
    async def test_tamper_middle_of_chain(self) -> None:
        records = _make_chain([
            {"a": 1},
            {"b": 2},
            {"c": 3},
            {"d": 4},
            {"e": 5},
        ])
        # Tamper with record 3
        records[3].entry_hash = "bad"

        verifier = AuditIntegrityVerifier.__new__(AuditIntegrityVerifier)
        verifier._session = MagicMock(return_value=_mock_session_context(records))

        result = await verifier.verify()

        assert not result.is_valid
        assert result.records_checked == 4
        assert result.first_broken_link == "evt-3"
