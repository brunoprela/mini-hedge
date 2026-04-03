"""FGA resource type declarations.

Each ResourceType must match a type_definition in ``fga_model.json``.
Startup validation (:func:`~app.shared.fga.validate_resource_registry`)
will fail fast if these drift out of sync.

To add a new resource type:
1. Add the type definition to ``app/modules/platform/fga_model.json``
2. Register it here with :func:`~app.shared.fga.register_resource_type`
3. Use ``MyResource.relation("can_view")`` with :func:`~app.shared.fga.require_access` in routes
"""

from app.shared.fga import ResourceType, register_resource_type

Portfolio = register_resource_type(
    ResourceType(
        name="portfolio",
        relations=frozenset({"can_view", "can_trade", "can_manage"}),
    )
)

Fund = register_resource_type(
    ResourceType(
        name="fund",
        relations=frozenset({
            "admin", "portfolio_manager", "analyst", "risk_manager",
            "compliance", "viewer", "ops_full", "ops_read",
            "can_admin", "can_read",
        }),
    )
)

Platform = register_resource_type(
    ResourceType(
        name="platform",
        relations=frozenset({"ops_admin", "ops_viewer"}),
    )
)
