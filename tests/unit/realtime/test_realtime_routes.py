"""Unit tests for the realtime SSE streaming endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.realtime.routes.realtime import (
    _HEARTBEAT_INTERVAL,
    _event_stream,
    stream_events,
)


def _make_request(redis=None, fund_slug: str | None = None) -> MagicMock:
    req = MagicMock()
    req.app.state.redis = redis
    req.is_disconnected = AsyncMock(return_value=False)
    return req


def _make_pubsub(messages: list[dict | None] | None = None) -> AsyncMock:
    """Create a mock Redis pubsub that yields the given messages then blocks."""
    ps = AsyncMock()
    ps.subscribe = AsyncMock()
    ps.unsubscribe = AsyncMock()
    ps.aclose = AsyncMock()

    if messages is None:
        messages = []

    call_count = 0

    async def _get_message(**kwargs):
        nonlocal call_count
        if call_count < len(messages):
            msg = messages[call_count]
            call_count += 1
            return msg
        # After exhausting messages, raise CancelledError to stop the loop
        raise asyncio.CancelledError

    ps.get_message = AsyncMock(side_effect=_get_message)
    return ps


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_no_redis_returns_503(self) -> None:
        req = _make_request(redis=None)

        with patch("app.modules.realtime.routes.realtime.get_actor_context"):
            resp = await stream_events(req, token="jwt", fund_slug=None)

        assert resp.status_code == 503
        body = b""
        async for chunk in resp.body_iterator:
            body += chunk.encode() if isinstance(chunk, str) else chunk
        assert b"not available" in body

    @pytest.mark.asyncio
    async def test_with_redis_returns_sse_stream(self) -> None:
        redis = MagicMock()
        req = _make_request(redis=redis)

        ctx = MagicMock()
        ctx.fund_slug = "alpha"

        with patch("app.modules.realtime.routes.realtime.get_actor_context", return_value=ctx):
            resp = await stream_events(req, token="jwt", fund_slug=None)

        assert resp.status_code == 200
        assert resp.media_type == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache"
        assert resp.headers["X-Accel-Buffering"] == "no"

    @pytest.mark.asyncio
    async def test_no_fund_slug_only_prices_channel(self) -> None:
        redis = MagicMock()
        req = _make_request(redis=redis)

        ctx = MagicMock()
        ctx.fund_slug = None

        with patch("app.modules.realtime.routes.realtime.get_actor_context", return_value=ctx):
            resp = await stream_events(req, token="jwt", fund_slug=None)

        assert resp.status_code == 200


class TestEventStream:
    @pytest.mark.asyncio
    async def test_yields_sse_formatted_message(self) -> None:
        payload = {"event_type": "price_update", "instrument": "AAPL", "price": 150}
        messages = [
            {"type": "message", "data": json.dumps(payload)},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)

        req = _make_request(redis=redis)
        req.app.state.redis = redis

        chunks = []
        async for chunk in _event_stream(req, ["shared:prices"]):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].startswith("event: price_update\n")
        assert '"AAPL"' in chunks[0]

        pubsub.subscribe.assert_called_once_with("shared:prices")
        pubsub.unsubscribe.assert_called_once_with("shared:prices")
        pubsub.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_event_type_when_missing(self) -> None:
        payload = {"instrument": "MSFT", "price": 300}
        messages = [
            {"type": "message", "data": json.dumps(payload)},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["shared:prices"]):
            chunks.append(chunk)

        assert chunks[0].startswith("event: message\n")

    @pytest.mark.asyncio
    async def test_non_string_data_passed_through(self) -> None:
        """When data is already a dict (not a string), it's used directly."""
        payload = {"event_type": "fill", "order_id": "123"}
        messages = [
            {"type": "message", "data": payload},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["ch1"]):
            chunks.append(chunk)

        assert "event: fill\n" in chunks[0]

    @pytest.mark.asyncio
    async def test_skips_non_message_types(self) -> None:
        messages = [
            {"type": "subscribe", "data": None},  # should be skipped
            {"type": "message", "data": json.dumps({"event_type": "tick"})},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["ch1"]):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert "event: tick\n" in chunks[0]

    @pytest.mark.asyncio
    async def test_none_message_skipped(self) -> None:
        messages = [
            None,  # no message ready
            {"type": "message", "data": json.dumps({"event_type": "update"})},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["ch1"]):
            chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_on_timeout(self) -> None:
        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()

        call_count = 0

        async def _get_message(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError
            raise asyncio.CancelledError

        pubsub.get_message = AsyncMock(side_effect=_get_message)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["ch1"]):
            chunks.append(chunk)

        assert chunks[0] == ": heartbeat\n\n"

    @pytest.mark.asyncio
    async def test_disconnected_client_stops_stream(self) -> None:
        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()
        pubsub.get_message = AsyncMock(return_value=None)

        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)

        req = _make_request(redis=redis)
        req.is_disconnected = AsyncMock(return_value=True)

        chunks = []
        async for chunk in _event_stream(req, ["ch1"]):
            chunks.append(chunk)

        assert chunks == []
        pubsub.unsubscribe.assert_called_once()
        pubsub.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_channels(self) -> None:
        messages = [
            {"type": "message", "data": json.dumps({"event_type": "nav"})},
        ]
        pubsub = _make_pubsub(messages)
        redis = MagicMock()
        redis.pubsub = MagicMock(return_value=pubsub)
        req = _make_request(redis=redis)

        chunks = []
        async for chunk in _event_stream(req, ["shared:prices", "fund:alpha"]):
            chunks.append(chunk)

        pubsub.subscribe.assert_called_once_with("shared:prices", "fund:alpha")
        pubsub.unsubscribe.assert_called_once_with("shared:prices", "fund:alpha")


class TestRouteImports:
    def test_router_reexported(self) -> None:
        from app.modules.realtime.routes import router

        assert router is not None
