"""Audit subpackage — event types, CDC processing, bridging, and archival.

Re-exports all public symbols for convenient access::

    from app.shared.audit import AuditEventType, AuditBridge, CdcTransformer
"""

from app.shared.audit.archival import ArchivalResult, MinioArchiver
from app.shared.audit.archival_service import ArchivalService
from app.shared.audit.bridge import AuditBridge
from app.shared.audit.cdc_consumer import CdcAuditConsumer
from app.shared.audit.cdc_transformer import CdcTransformer
from app.shared.audit.events import AuditEventType

__all__ = [
    "ArchivalResult",
    "ArchivalService",
    "AuditBridge",
    "AuditEventType",
    "CdcAuditConsumer",
    "CdcTransformer",
    "MinioArchiver",
]
