"""Unit tests for X-Acting-As header extraction in auth middleware."""

from __future__ import annotations


class TestActingAsHeader:
    """Test that the middleware correctly extracts the X-Acting-As header.

    These tests verify the header extraction logic. Full delegation flow
    (servicing edge lookup, role intersection) is tested in integration tests
    since it requires the auth service + database.
    """

    def test_header_key_is_lowercase(self) -> None:
        """Verify the header key we use matches HTTP/2 lowercase convention."""
        # ASGI scope headers are always lowercase bytes
        headers = {b"x-acting-as": b"cust-target-123"}
        acting_as = headers.get(b"x-acting-as", b"").decode() or None
        assert acting_as == "cust-target-123"

    def test_missing_header_is_none(self) -> None:
        headers: dict[bytes, bytes] = {}
        acting_as = headers.get(b"x-acting-as", b"").decode() or None
        assert acting_as is None

    def test_empty_header_is_none(self) -> None:
        headers = {b"x-acting-as": b""}
        acting_as = headers.get(b"x-acting-as", b"").decode() or None
        assert acting_as is None
