"""Re-export for backwards compatibility. Import from auth_service directly."""

from app.modules.platform.auth_service import AuthService

__all__ = ["AuthService"]
