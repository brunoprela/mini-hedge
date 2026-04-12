"""Unit tests for instrument CRUD API routes (POST/PATCH)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.modules.security_master.routes.security_master import (
    CreateInstrumentRequest,
    UpdateInstrumentRequest,
)


class TestCreateInstrumentRequest:
    def test_valid_request(self) -> None:
        req = CreateInstrumentRequest(
            name="Apple Inc.",
            ticker="AAPL",
            asset_class="equity",
            currency="USD",
            exchange="NASDAQ",
            country="US",
            sector="Technology",
            industry="Consumer Electronics",
        )
        assert req.name == "Apple Inc."
        assert req.ticker == "AAPL"

    def test_optional_fields(self) -> None:
        req = CreateInstrumentRequest(
            name="Test Corp",
            ticker="TEST",
            asset_class="equity",
            currency="USD",
            exchange="NYSE",
            country="US",
        )
        assert req.sector is None
        assert req.industry is None


class TestUpdateInstrumentRequest:
    def test_partial_update(self) -> None:
        req = UpdateInstrumentRequest(name="New Name")
        updates = req.model_dump(exclude_none=True)
        assert updates == {"name": "New Name"}

    def test_empty_update(self) -> None:
        req = UpdateInstrumentRequest()
        updates = req.model_dump(exclude_none=True)
        assert updates == {}

    def test_multiple_fields(self) -> None:
        req = UpdateInstrumentRequest(name="New Name", sector="Technology")
        updates = req.model_dump(exclude_none=True)
        assert updates == {"name": "New Name", "sector": "Technology"}
