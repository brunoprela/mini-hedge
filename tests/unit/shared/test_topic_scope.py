"""Unit tests for TopicScope enum, customer-scoped topics, and acted_on_behalf_of."""

from __future__ import annotations

from app.shared.events import BaseEvent
from app.shared.schema_registry import (
    TopicScope,
    base_topic_name,
    customer_topic,
    fund_topic,
    shared_topic,
)


class TestTopicScope:
    def test_enum_values(self) -> None:
        assert TopicScope.FUND == "fund"
        assert TopicScope.CUSTOMER == "customer"
        assert TopicScope.CELL == "cell"

    def test_all_scopes_defined(self) -> None:
        assert len(TopicScope) == 3


class TestCustomerTopic:
    def test_format(self) -> None:
        topic = customer_topic("cust-123", "alpha", "positions.changed")
        assert topic == "customer-cust-123.fund-alpha.positions.changed"

    def test_different_customers_different_topics(self) -> None:
        t1 = customer_topic("cust-1", "alpha", "orders.created")
        t2 = customer_topic("cust-2", "alpha", "orders.created")
        assert t1 != t2

    def test_different_funds_different_topics(self) -> None:
        t1 = customer_topic("cust-1", "alpha", "orders.created")
        t2 = customer_topic("cust-1", "beta", "orders.created")
        assert t1 != t2


class TestExistingTopicFunctions:
    def test_shared_topic(self) -> None:
        assert shared_topic("prices.normalized") == "shared.prices.normalized"

    def test_fund_topic(self) -> None:
        assert fund_topic("alpha", "positions.changed") == "fund-alpha.positions.changed"

    def test_base_topic_from_shared(self) -> None:
        assert base_topic_name("shared.prices.normalized") == "prices.normalized"

    def test_base_topic_from_fund(self) -> None:
        assert base_topic_name("fund-alpha.positions.changed") == "positions.changed"

    def test_base_topic_passthrough(self) -> None:
        assert base_topic_name("prices.normalized") == "prices.normalized"


class TestActedOnBehalfOf:
    def test_default_is_none(self) -> None:
        event = BaseEvent(event_type="test", data={})
        assert event.acted_on_behalf_of is None

    def test_set_delegated_actor(self) -> None:
        event = BaseEvent(
            event_type="order.created",
            data={"order_id": "123"},
            actor_id="ops-user-1",
            acted_on_behalf_of="fund-manager-1",
        )
        assert event.acted_on_behalf_of == "fund-manager-1"
        assert event.actor_id == "ops-user-1"

    def test_serialization_includes_field(self) -> None:
        event = BaseEvent(
            event_type="test",
            data={},
            acted_on_behalf_of="delegated-user",
        )
        d = event.model_dump()
        assert "acted_on_behalf_of" in d
        assert d["acted_on_behalf_of"] == "delegated-user"
