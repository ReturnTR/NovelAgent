"""Tests for API routes"""
import pytest


class TestAgentsRoutes:
    """Test /api/agents routes"""

    def test_routes_module_importable(self):
        """Routes module should be importable"""
        from web_console.backend.routes import agents_router, sessions_router, registry_router, chat_router
        assert agents_router is not None
        assert sessions_router is not None
        assert registry_router is not None
        assert chat_router is not None

    def test_agents_router_has_expected_routes(self):
        """Agents router should have expected route handlers"""
        from web_console.backend.routes.agents import router
        assert len(router.routes) > 0

    def test_sessions_router_has_expected_routes(self):
        """Sessions router should have expected route handlers"""
        from web_console.backend.routes.sessions import router
        assert len(router.routes) > 0

    def test_registry_router_has_expected_routes(self):
        """Registry router should have expected route handlers"""
        from web_console.backend.routes.registry import router
        assert len(router.routes) > 0

    def test_chat_router_has_expected_routes(self):
        """Chat router should have expected route handlers"""
        from web_console.backend.routes.chat import router
        assert len(router.routes) > 0
