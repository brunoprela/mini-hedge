from .admin import router as admin_router
from .archival import router as archival_router
from .dlq import router as dlq_router
from .health import router as health_router
from .platform import router

__all__ = ["admin_router", "archival_router", "dlq_router", "health_router", "router"]
