"""Store clients and bridges — Redis, immudb, OpenSearch."""

from app.shared.stores.immudb_bridge import ImmudbBridge
from app.shared.stores.immudb_client import ImmudbClient
from app.shared.stores.immudb_verifier import VerificationResult, verify_audit_batch
from app.shared.stores.opensearch_bridge import OpenSearchBridge
from app.shared.stores.opensearch_client import OpenSearchClient
from app.shared.stores.redis import create_redis_client
from app.shared.stores.redis_bridge import (
    PRICES_CHANNEL,
    RedisBridge,
    fund_channel,
)

__all__ = [
    "PRICES_CHANNEL",
    "ImmudbBridge",
    "ImmudbClient",
    "OpenSearchBridge",
    "OpenSearchClient",
    "RedisBridge",
    "VerificationResult",
    "create_redis_client",
    "fund_channel",
    "verify_audit_batch",
]
