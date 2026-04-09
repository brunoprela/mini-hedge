"""Unit tests for DLQ management data structures."""

from __future__ import annotations

from app.shared.dlq_manager import DlqMessage, DlqTopicInfo, ReplayResult


class TestDlqTopicInfo:
    def test_source_topic_derived(self) -> None:
        info = DlqTopicInfo(
            topic="fund-alpha.trades.executed.dlq",
            source_topic="fund-alpha.trades.executed",
            message_count=5,
        )
        assert info.source_topic == "fund-alpha.trades.executed"
        assert info.message_count == 5


class TestDlqMessage:
    def test_json_value(self) -> None:
        msg = DlqMessage(
            offset=42,
            timestamp=1705312200000,
            key="AAPL",
            value={"event_type": "trades.executed", "data": {"qty": 100}},
        )
        assert msg.offset == 42
        assert isinstance(msg.value, dict)

    def test_string_value(self) -> None:
        msg = DlqMessage(offset=0, timestamp=None, key=None, value="unparseable")
        assert msg.value == "unparseable"


class TestReplayResult:
    def test_replay_summary(self) -> None:
        result = ReplayResult(
            topic="fund-alpha.trades.executed.dlq",
            source_topic="fund-alpha.trades.executed",
            replayed=8,
            failed=2,
        )
        assert result.replayed == 8
        assert result.failed == 2
