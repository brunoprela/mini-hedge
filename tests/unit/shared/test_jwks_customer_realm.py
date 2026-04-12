"""Unit tests for per-customer JWKS realm resolution."""

from __future__ import annotations

from app.shared.auth.jwt import (
    _customer_realm_map,
    configure_customer_realms,
    resolve_customer_realm,
)


class TestConfigureCustomerRealms:
    def setup_method(self) -> None:
        _customer_realm_map.clear()

    def teardown_method(self) -> None:
        _customer_realm_map.clear()

    def test_configure_populates_map(self) -> None:
        configure_customer_realms({
            "cust-1": {"realm": "cust1-realm", "client_id": "cust1-client"},
        })
        assert "cust-1" in _customer_realm_map
        assert _customer_realm_map["cust-1"]["realm"] == "cust1-realm"

    def test_configure_clears_previous(self) -> None:
        configure_customer_realms({"cust-1": {"realm": "r1", "client_id": "c1"}})
        configure_customer_realms({"cust-2": {"realm": "r2", "client_id": "c2"}})
        assert "cust-1" not in _customer_realm_map
        assert "cust-2" in _customer_realm_map

    def test_configure_empty_map(self) -> None:
        configure_customer_realms({"cust-1": {"realm": "r1", "client_id": "c1"}})
        configure_customer_realms({})
        assert len(_customer_realm_map) == 0


class TestResolveCustomerRealm:
    def setup_method(self) -> None:
        _customer_realm_map.clear()
        configure_customer_realms({
            "cust-abc": {"realm": "abc-realm", "client_id": "abc-client"},
            "cust-partial": {"realm": "partial-realm"},
        })

    def teardown_method(self) -> None:
        _customer_realm_map.clear()

    def test_known_customer_returns_custom_realm(self) -> None:
        realm, client_id = resolve_customer_realm(
            "cust-abc",
            default_realm="minihedge",
            default_client_id="mini-hedge-ui",
        )
        assert realm == "abc-realm"
        assert client_id == "abc-client"

    def test_unknown_customer_returns_defaults(self) -> None:
        realm, client_id = resolve_customer_realm(
            "cust-unknown",
            default_realm="minihedge",
            default_client_id="mini-hedge-ui",
        )
        assert realm == "minihedge"
        assert client_id == "mini-hedge-ui"

    def test_none_customer_returns_defaults(self) -> None:
        realm, client_id = resolve_customer_realm(
            None,
            default_realm="minihedge",
            default_client_id="mini-hedge-ui",
        )
        assert realm == "minihedge"
        assert client_id == "mini-hedge-ui"

    def test_empty_string_customer_returns_defaults(self) -> None:
        realm, client_id = resolve_customer_realm(
            "",
            default_realm="minihedge",
            default_client_id="mini-hedge-ui",
        )
        assert realm == "minihedge"
        assert client_id == "mini-hedge-ui"

    def test_partial_config_falls_back_for_missing_client_id(self) -> None:
        realm, client_id = resolve_customer_realm(
            "cust-partial",
            default_realm="minihedge",
            default_client_id="mini-hedge-ui",
        )
        assert realm == "partial-realm"
        assert client_id == "mini-hedge-ui"
