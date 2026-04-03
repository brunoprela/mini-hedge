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
        relations=frozenset(
            {
                "admin",
                "portfolio_manager",
                "analyst",
                "risk_manager",
                "compliance_officer",
                "viewer",
                "ops_full",
                "ops_read",
                "can_admin",
                "can_read",
                # Per-user permission relations (directly assignable + computed from roles)
                "can_read_instruments",
                "can_write_instruments",
                "can_read_prices",
                "can_read_positions",
                "can_write_positions",
                "can_execute_trades",
                "can_read_fund",
                "can_manage_fund",
                # Phase 2: Orders, Compliance, Exposure
                "can_read_orders",
                "can_create_orders",
                "can_cancel_orders",
                "can_read_compliance",
                "can_manage_compliance",
                "can_read_exposure",
            }
        ),
    )
)

Platform = register_resource_type(
    ResourceType(
        name="platform",
        relations=frozenset({"ops_admin", "ops_viewer"}),
    )
)
