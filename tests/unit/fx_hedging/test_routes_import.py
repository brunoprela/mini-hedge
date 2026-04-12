"""Test that FX hedging routes module can be imported (covers decorators and definitions)."""

from __future__ import annotations


class TestRoutesImport:
    def test_router_is_importable(self) -> None:
        from app.modules.fx_hedging.routes.fx_hedging import router

        assert router is not None
        # Verify the router has the expected prefix
        assert router.prefix == "/fx-hedging"

    def test_routes_init_exports_router(self) -> None:
        from app.modules.fx_hedging.routes import router

        assert router is not None
