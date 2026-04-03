"""Unit tests for schema_registry topic naming and Avro serialization."""

from app.shared.schema_registry import (
    base_topic_name,
    fund_topic,
    fund_topics_for_slug,
    shared_topic,
    shared_topics,
)


class TestTopicNaming:
    def test_shared_topic(self) -> None:
        assert shared_topic("prices.normalized") == "shared.prices.normalized"

    def test_fund_topic(self) -> None:
        assert fund_topic("alpha", "positions.changed") == "fund-alpha.positions.changed"

    def test_base_topic_strips_shared_prefix(self) -> None:
        assert base_topic_name("shared.prices.normalized") == "prices.normalized"

    def test_base_topic_strips_fund_prefix(self) -> None:
        assert base_topic_name("fund-alpha.positions.changed") == "positions.changed"
        assert base_topic_name("fund-beta.pnl.realized") == "pnl.realized"
        assert base_topic_name("fund-gamma.trades.executed") == "trades.executed"

    def test_base_topic_passthrough(self) -> None:
        assert base_topic_name("prices.normalized") == "prices.normalized"

    def test_fund_topics_for_slug(self) -> None:
        topics = fund_topics_for_slug("alpha")
        assert len(topics) == 3
        assert "fund-alpha.positions.changed" in topics
        assert "fund-alpha.pnl.realized" in topics
        assert "fund-alpha.trades.executed" in topics

    def test_shared_topics(self) -> None:
        topics = shared_topics()
        assert "shared.prices.normalized" in topics


class TestAvroSerialization:
    def test_roundtrip_price_event(self) -> None:
        from app.shared.schema_registry import (
            deserialize_event,
            load_schemas,
            serialize_event,
        )

        load_schemas()

        envelope = {
            "event_id": "test-123",
            "event_type": "price.updated",
            "event_version": 1,
            "timestamp": "2026-04-02T12:00:00Z",
            "actor_id": None,
            "actor_type": None,
            "fund_slug": None,
        }
        payload = {
            "instrument_id": "AAPL",
            "bid": "185.00",
            "ask": "185.50",
            "mid": "185.25",
            "timestamp": "2026-04-02T12:00:00Z",
            "source": "test",
        }

        raw = serialize_event("shared.prices.normalized", envelope, payload)
        assert isinstance(raw, bytes)
        assert len(raw) > 0

        decoded_env, decoded_payload = deserialize_event("shared.prices.normalized", raw)
        assert decoded_env["event_id"] == "test-123"
        assert decoded_payload["instrument_id"] == "AAPL"
        assert decoded_payload["mid"] == "185.25"

    def test_roundtrip_position_changed(self) -> None:
        from app.shared.schema_registry import (
            deserialize_event,
            load_schemas,
            serialize_event,
        )

        load_schemas()

        envelope = {
            "event_id": "test-456",
            "event_type": "position.changed",
            "event_version": 1,
            "timestamp": "2026-04-02T12:00:00Z",
            "actor_id": "user-1",
            "actor_type": "user",
            "fund_slug": "alpha",
        }
        payload = {
            "portfolio_id": "20000000-0000-0000-0000-000000000001",
            "instrument_id": "MSFT",
            "quantity": "100",
            "avg_cost": "410.00",
            "cost_basis": "41000.00",
        }

        # Fund-scoped topic resolves to positions.changed schema
        topic = "fund-alpha.positions.changed"
        raw = serialize_event(topic, envelope, payload)
        decoded_env, decoded_payload = deserialize_event(topic, raw)
        assert decoded_payload["portfolio_id"] == "20000000-0000-0000-0000-000000000001"
        assert decoded_payload["quantity"] == "100"

    def test_roundtrip_pnl_realized(self) -> None:
        from app.shared.schema_registry import (
            deserialize_event,
            load_schemas,
            serialize_event,
        )

        load_schemas()

        envelope = {
            "event_id": "test-789",
            "event_type": "pnl.realized",
            "event_version": 1,
            "timestamp": "2026-04-02T12:00:00Z",
            "actor_id": None,
            "actor_type": None,
            "fund_slug": "beta",
        }
        payload = {
            "portfolio_id": "20000000-0000-0000-0000-000000000010",
            "instrument_id": "GS",
            "realized_pnl": "1500.00",
            "price": "460.00",
        }

        topic = "fund-beta.pnl.realized"
        raw = serialize_event(topic, envelope, payload)
        decoded_env, decoded_payload = deserialize_event(topic, raw)
        assert decoded_payload["realized_pnl"] == "1500.00"

    def test_roundtrip_trade_executed(self) -> None:
        from app.shared.schema_registry import (
            deserialize_event,
            load_schemas,
            serialize_event,
        )

        load_schemas()

        envelope = {
            "event_id": "test-trade",
            "event_type": "trade.buy",
            "event_version": 1,
            "timestamp": "2026-04-02T12:00:00Z",
            "actor_id": "pm-1",
            "actor_type": "user",
            "fund_slug": "gamma",
        }
        payload = {
            "portfolio_id": "20000000-0000-0000-0000-000000000020",
            "instrument_id": "TSLA",
            "side": "buy",
            "quantity": "50",
            "price": "250.00",
            "trade_id": "trade-001",
            "currency": "USD",
        }

        topic = "fund-gamma.trades.executed"
        raw = serialize_event(topic, envelope, payload)
        decoded_env, decoded_payload = deserialize_event(topic, raw)
        assert decoded_payload["side"] == "buy"
        assert decoded_payload["trade_id"] == "trade-001"
