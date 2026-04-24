"""Route modules for web console API"""
from .agents import router as agents_router
from .sessions import router as sessions_router
from .registry import router as registry_router
from .chat import router as chat_router

__all__ = ["agents_router", "sessions_router", "registry_router", "chat_router"]