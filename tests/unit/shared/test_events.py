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

    @pytest.mark.asyncio
    async def test_failing_handler_does_not_break_others(self) -> None:
        """Error isolation: one handler raising should not prevent others.

        All handlers run to completion (gather), then failures are surfaced
        as an ExceptionGroup so callers know something went wrong.
        """
        bus = InProcessEventBus()
        received: list[BaseEvent] = []

        async def bad_handler(event: BaseEvent) -> None:
            raise RuntimeError("boom")

        async def good_handler(event: BaseEvent) -> None:
            received.append(event)

        bus.subscribe("test.topic", bad_handler)
        bus.subscribe("test.topic", good_handler)

        with pytest.raises(ExceptionGroup) as exc_info:
            await bus.publish("test.topic", BaseEvent(event_type="test", data={}))

        # Good handler still ran despite the bad one
        assert len(received) == 1
        # The error is surfaced, not swallowed
        assert len(exc_info.value.exceptions) == 1
        assert isinstance(exc_info.value.exceptions[0], RuntimeError)
