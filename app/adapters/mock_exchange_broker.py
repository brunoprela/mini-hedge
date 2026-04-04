"""Mock-exchange broker adapter — submits orders via HTTP, receives fills via Kafka.

The mock-exchange is an external vendor with its own Kafka cluster.
Order submission goes via REST (HTTP POST). Execution reports (fills)
arrive asynchronously on the vendor's Kafka topic and are bridged
into the platform via a callback to OrderService.

This is the same pattern a real FIX broker or IB TWS adapter would use:
submit orders via the vendor's API, receive fills on a separate channel.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from functools import partial

import httpx
import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException

from app.shared.adapters import OrderAcknowledgement, OrderStatusReport

logger = structlog.get_logger()

# Topic on the external vendor's Kafka cluster
_EXTERNAL_EXECUTION_REPORTS_TOPIC = "shared.execution-reports"

# Callback type: (client_order_id, fill_price, fill_quantity, filled_at) -> None
FillCallback = Callable[[str, Decimal, Decimal, datetime | None], Awaitable[None]]


class MockExchangeBrokerAdapter:
    """BrokerAdapter backed by the mock-exchange service.

    Order submission: HTTP POST to mock-exchange REST API.
    Fill reception: Kafka consumer on vendor's cluster for execution reports.
    """

    def __init__(
        self,
        *,
        base_url: str,
        kafka_bootstrap_servers: str,
    ) -> None:
        self._base_url = base_url
        self._kafka_servers = kafka_bootstrap_servers
        self._running = False
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # BrokerAdapter protocol methods
    # ------------------------------------------------------------------

    async def submit_order(
        self,
        client_order_id: str,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
    ) -> OrderAcknowledgement:
        body = {
            "client_order_id": client_order_id,
            "instrument_id": instrument_id,
            "side": side,
            "quantity": str(quantity),
            "order_type": order_type,
        }
        if limit_price is not None:
            body["limit_price"] = str(limit_price)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.post("/api/v1/orders", json=body)
            resp.raise_for_status()
            data = resp.json()

        return OrderAcknowledgement(
            exchange_order_id=data["exchange_order_id"],
            client_order_id=data["client_order_id"],
            status=data["status"],
            received_at=datetime.fromisoformat(data["received_at"]),
        )

    async def cancel_order(self, exchange_order_id: str) -> bool:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.delete(f"/api/v1/orders/{exchange_order_id}")
            return resp.status_code == 200

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusReport:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.get(f"/api/v1/orders/{exchange_order_id}")
            resp.raise_for_status()
            data = resp.json()

        return OrderStatusReport(
            exchange_order_id=data["exchange_order_id"],
            client_order_id=data["client_order_id"],
            status=data["status"],
            filled_quantity=Decimal(data.get("filled_quantity", "0")),
            avg_fill_price=Decimal(data["avg_fill_price"]) if data.get("avg_fill_price") else None,
        )

    # ------------------------------------------------------------------
    # Execution report consumer (vendor Kafka → platform callback)
    # ------------------------------------------------------------------

    async def start_fill_consumer(self, callback: FillCallback) -> None:
        """Start consuming execution reports from the vendor's Kafka.

        Each fill is translated and forwarded to the callback, which is
        typically ``OrderService.process_execution_report``.
        """
        self._running = True
        self._task = asyncio.create_task(
            self._consume_execution_reports(callback),
            name="mock-exchange-fill-bridge",
        )
        logger.info("mock_exchange_fill_consumer_started", kafka=self._kafka_servers)

    async def stop_fill_consumer(self) -> None:
        """Stop the execution report consumer."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("mock_exchange_fill_consumer_stopped")

    async def _consume_execution_reports(self, callback: FillCallback) -> None:
        """Poll the vendor's Kafka for execution reports and dispatch fills."""
        consumer = Consumer(
            {
                "bootstrap.servers": self._kafka_servers,
                "group.id": "minihedge-external-fills",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
                # Discover newly auto-created topics quickly (default 5 min)
                "topic.metadata.refresh.interval.ms": 10000,
            }
        )
        consumer.subscribe([_EXTERNAL_EXECUTION_REPORTS_TOPIC])
        loop = asyncio.get_running_loop()

        try:
            while self._running:
                try:
                    msg = await loop.run_in_executor(
                        None,
                        partial(consumer.poll, 1.0),
                    )
                except KafkaException:
                    logger.exception("external_kafka_fill_poll_error")
                    await asyncio.sleep(1)
                    continue

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("external_kafka_fill_error", error=str(msg.error()))
                    continue

                try:
                    envelope = json.loads(msg.value())
                    data = envelope["data"]

                    # Only process actual fills (not acks or rejects)
                    status = data.get("status", "")
                    if status not in ("filled", "partially_filled"):
                        if status in ("rejected", "cancelled"):
                            logger.warning(
                                "execution_report_non_fill",
                                client_order_id=data.get("client_order_id"),
                                status=status,
                            )
                        continue

                    client_order_id = data["client_order_id"]
                    fill_price = Decimal(data["fill_price"])
                    fill_quantity = Decimal(data["fill_quantity"])

                    # Parse exchange fill timestamp if available
                    raw_filled_at = data.get("filled_at")
                    filled_at = datetime.fromisoformat(raw_filled_at) if raw_filled_at else None

                    await callback(client_order_id, fill_price, fill_quantity, filled_at)

                    logger.debug(
                        "execution_report_bridged",
                        client_order_id=client_order_id,
                        fill_price=str(fill_price),
                        fill_quantity=str(fill_quantity),
                    )
                except Exception:
                    logger.exception("execution_report_bridge_failed")
        finally:
            consumer.close()
