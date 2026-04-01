"""Unit tests for the in-process event bus."""

import pytest

from app.shared.events import BaseEvent, InProcessEventBus


class TestInProcessEventBus:
    @pytest.mark.asyncio
    async def test_publish_to_subscriber(self) -> None:
        bus = InProcessEventBus()
        received: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received.append(event)

        bus.subscribe("test.topic", handler)
        event = BaseEvent(event_type="test", data={"key": "value"})
        await bus.publish("test.topic", event)

        assert len(received) == 1
        assert received[0].data["key"] == "value"

    @pytest.mark.asyncio
    async def test_no_subscribers_no_error(self) -> None:
        bus = InProcessEventBus()
        event = BaseEvent(event_type="test", data={})
        await bus.publish("test.topic", event)  # should not raise

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bus = InProcessEventBus()
        count = [0, 0]

        async def handler_a(event: BaseEvent) -> None:
            count[0] += 1

        async def handler_b(event: BaseEvent) -> None:
            count[1] += 1

        bus.subscribe("test.topic", handler_a)
        bus.subscribe("test.topic", handler_b)
        await bus.publish("test.topic", BaseEvent(event_type="test", data={}))

        assert count == [1, 1]
