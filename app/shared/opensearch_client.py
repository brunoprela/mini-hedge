"""Async OpenSearch client for audit log indexing and search.

Wraps the ``opensearch-py`` async client to provide audit-specific
operations: indexing events, searching by time range / actor / entity,
and aggregations for compliance dashboards.

Index naming follows the schema-per-fund pattern: ``audit-fund-alpha``,
``audit-fund-beta``.  Events without a fund_slug go to ``audit-platform``.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

# Default index settings for audit indices
_INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,  # single-node local dev
        "refresh_interval": "5s",
    },
    "mappings": {
        "properties": {
            "event_id": {"type": "keyword"},
            "event_type": {"type": "keyword"},
            "event_version": {"type": "integer"},
            "timestamp": {"type": "date"},
            "actor_id": {"type": "keyword"},
            "actor_type": {"type": "keyword"},
            "fund_slug": {"type": "keyword"},
            "data": {"type": "object", "enabled": True},
            "data_text": {"type": "text"},  # full-text searchable
        }
    },
}


def _index_name(fund_slug: str | None) -> str:
    """Map fund slug to OpenSearch index name."""
    if fund_slug:
        return f"audit-fund-{fund_slug}"
    return "audit-platform"


class OpenSearchClient:
    """Audit-focused async OpenSearch client."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 9200,
        username: str = "admin",
        password: str = "admin",
        use_ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._client: Any | None = None
        self._ensured_indices: set[str] = set()

    async def connect(self) -> None:
        """Create the async OpenSearch client."""
        from opensearchpy import AsyncOpenSearch

        self._client = AsyncOpenSearch(
            hosts=[{"host": self._host, "port": self._port}],
            http_auth=(self._username, self._password),
            use_ssl=self._use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
        )
        logger.info(
            "opensearch_connected",
            host=self._host,
            port=self._port,
        )

    async def _ensure_index(self, index: str) -> None:
        """Create index if it doesn't exist (lazy, cached per session)."""
        if index in self._ensured_indices:
            return
        assert self._client is not None

        exists = await self._client.indices.exists(index=index)
        if not exists:
            await self._client.indices.create(index=index, body=_INDEX_SETTINGS)
            logger.info("opensearch_index_created", index=index)

        self._ensured_indices.add(index)

    async def index_event(
        self,
        *,
        event_id: str,
        event_type: str,
        event_version: int,
        timestamp: str,
        actor_id: str | None,
        actor_type: str | None,
        fund_slug: str | None,
        data: dict[str, Any],
    ) -> None:
        """Index a single audit event."""
        assert self._client is not None

        import json

        index = _index_name(fund_slug)
        await self._ensure_index(index)

        doc = {
            "event_id": event_id,
            "event_type": event_type,
            "event_version": event_version,
            "timestamp": timestamp,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "fund_slug": fund_slug,
            "data": data,
            "data_text": json.dumps(data, default=str),
        }

        await self._client.index(
            index=index,
            id=event_id,
            body=doc,
        )

    async def search(
        self,
        *,
        fund_slug: str | None = None,
        query_text: str | None = None,
        event_type: str | None = None,
        actor_id: str | None = None,
        time_from: str | None = None,
        time_to: str | None = None,
        size: int = 50,
    ) -> list[dict[str, Any]]:
        """Search audit events with filters and full-text search."""
        assert self._client is not None

        index = _index_name(fund_slug) if fund_slug else "audit-*"

        must_clauses: list[dict[str, Any]] = []

        if query_text:
            must_clauses.append({"match": {"data_text": query_text}})
        if event_type:
            must_clauses.append({"term": {"event_type": event_type}})
        if actor_id:
            must_clauses.append({"term": {"actor_id": actor_id}})

        if time_from or time_to:
            range_clause: dict[str, str] = {}
            if time_from:
                range_clause["gte"] = time_from
            if time_to:
                range_clause["lte"] = time_to
            must_clauses.append({"range": {"timestamp": range_clause}})

        body: dict[str, Any] = {
            "size": size,
            "sort": [{"timestamp": {"order": "desc"}}],
        }
        if must_clauses:
            body["query"] = {"bool": {"must": must_clauses}}
        else:
            body["query"] = {"match_all": {}}

        result = await self._client.search(index=index, body=body)
        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def close(self) -> None:
        """Close the OpenSearch client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("opensearch_disconnected")
