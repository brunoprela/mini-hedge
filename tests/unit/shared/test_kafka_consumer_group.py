"""Unit tests for Kafka consumer group customer ID inclusion."""

from __future__ import annotations

from app.shared.kafka import KafkaEventBus


class TestConsumerGroupCustomerId:
    def test_default_group_without_customer(self) -> None:
        bus = KafkaEventBus("localhost:9092")
        assert bus._consumer_group == "minihedge"

    def test_group_includes_customer_id(self) -> None:
        bus = KafkaEventBus("localhost:9092", customer_id="cust-abc")
        assert bus._consumer_group == "minihedge-cust-abc"

    def test_custom_group_with_customer_id(self) -> None:
        bus = KafkaEventBus("localhost:9092", consumer_group="myapp", customer_id="cust-xyz")
        assert bus._consumer_group == "myapp-cust-xyz"

    def test_custom_group_without_customer(self) -> None:
        bus = KafkaEventBus("localhost:9092", consumer_group="myapp")
        assert bus._consumer_group == "myapp"

    def test_none_customer_id_same_as_default(self) -> None:
        bus = KafkaEventBus("localhost:9092", customer_id=None)
        assert bus._consumer_group == "minihedge"
