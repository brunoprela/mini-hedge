"""Shared test configuration and fixtures."""

import pytest


# Configure pytest-asyncio
def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    """Auto-mark tests in integration/ directory."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
