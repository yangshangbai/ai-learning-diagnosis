from .auth import router as auth_router
from .health import router as health_router
from .system_log import router as system_log_router

__all__ = ["health_router", "auth_router", "system_log_router"]
