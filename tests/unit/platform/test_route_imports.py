"""Test that route modules import cleanly and expose expected routers.

This covers the module-level code in routes/ files (router definitions,
Pydantic models, route decorators) without invoking any endpoint logic.
"""

from __future__ import annotations


class TestRouteImports:
    def test_platform_router_exists(self) -> None:
        from app.modules.platform.routes.platform import router

        assert router is not None
        assert len(router.routes) > 0

    def test_admin_router_exists(self) -> None:
        from app.modules.platform.routes.admin import router

        assert router is not None
        assert len(router.routes) > 0

    def test_archival_router_exists(self) -> None:
        from app.modules.platform.routes.archival import router

        assert router is not None

    def test_dlq_router_exists(self) -> None:
        from app.modules.platform.routes.dlq import router

        assert router is not None

    def test_routes_init_exports(self) -> None:
        from app.modules.platform.routes import (
            admin_router,
            archival_router,
            dlq_router,
            router,
        )

        assert router is not None
        assert admin_router is not None
        assert archival_router is not None
        assert dlq_router is not None
