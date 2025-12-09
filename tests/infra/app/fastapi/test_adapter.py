"""Tests for FastAPIAdapter."""

from unittest.mock import MagicMock, patch

import pytest

from appinfra.app.fastapi.config.api import ApiConfig
from appinfra.app.fastapi.runtime.adapter import (
    CORSDefinition,
    ExceptionHandlerDefinition,
    FastAPIAdapter,
    MiddlewareDefinition,
    RouteDefinition,
    RouterDefinition,
)


@pytest.mark.unit
class TestRouteDefinition:
    """Tests for RouteDefinition dataclass."""

    def test_default_values(self):
        """Test default values."""
        route = RouteDefinition(path="/test", handler=lambda: None)

        assert route.path == "/test"
        assert route.methods == ["GET"]
        assert route.response_model is None
        assert route.tags is None
        assert route.kwargs == {}

    def test_custom_values(self):
        """Test custom values."""
        handler = lambda: None
        route = RouteDefinition(
            path="/api/data",
            handler=handler,
            methods=["POST", "PUT"],
            response_model=dict,
            tags=["data"],
            kwargs={"summary": "Test endpoint"},
        )

        assert route.path == "/api/data"
        assert route.handler is handler
        assert route.methods == ["POST", "PUT"]
        assert route.response_model is dict
        assert route.tags == ["data"]
        assert route.kwargs == {"summary": "Test endpoint"}


@pytest.mark.unit
class TestRouterDefinition:
    """Tests for RouterDefinition dataclass."""

    def test_default_values(self):
        """Test default values."""
        router = MagicMock()
        router_def = RouterDefinition(router=router)

        assert router_def.router is router
        assert router_def.prefix == ""
        assert router_def.tags is None

    def test_custom_values(self):
        """Test custom values."""
        router = MagicMock()
        router_def = RouterDefinition(router=router, prefix="/api/v1", tags=["v1"])

        assert router_def.prefix == "/api/v1"
        assert router_def.tags == ["v1"]


@pytest.mark.unit
class TestMiddlewareDefinition:
    """Tests for MiddlewareDefinition dataclass."""

    def test_default_values(self):
        """Test default values."""

        class TestMiddleware:
            pass

        mw_def = MiddlewareDefinition(middleware_class=TestMiddleware)

        assert mw_def.middleware_class is TestMiddleware
        assert mw_def.options == {}

    def test_with_options(self):
        """Test with options."""

        class TestMiddleware:
            pass

        mw_def = MiddlewareDefinition(
            middleware_class=TestMiddleware, options={"timeout": 30}
        )

        assert mw_def.options == {"timeout": 30}


@pytest.mark.unit
class TestCORSDefinition:
    """Tests for CORSDefinition dataclass."""

    def test_default_values(self):
        """Test default values."""
        cors = CORSDefinition(origins=["http://localhost"])

        assert cors.origins == ["http://localhost"]
        assert cors.allow_credentials is False
        assert cors.allow_methods == ["*"]
        assert cors.allow_headers == ["*"]

    def test_custom_values(self):
        """Test custom values."""
        cors = CORSDefinition(
            origins=["http://example.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization"],
        )

        assert cors.origins == ["http://example.com"]
        assert cors.allow_credentials is True
        assert cors.allow_methods == ["GET", "POST"]
        assert cors.allow_headers == ["Authorization"]


@pytest.mark.unit
class TestExceptionHandlerDefinition:
    """Tests for ExceptionHandlerDefinition dataclass."""

    def test_values(self):
        """Test definition values."""

        def handler(request, exc):
            pass

        exc_def = ExceptionHandlerDefinition(exc_class=ValueError, handler=handler)

        assert exc_def.exc_class is ValueError
        assert exc_def.handler is handler


@pytest.mark.unit
class TestFastAPIAdapter:
    """Tests for FastAPIAdapter."""

    @pytest.fixture
    def mock_fastapi(self):
        """Mock FastAPI module."""
        with (
            patch("appinfra.app.fastapi.runtime.adapter.FASTAPI_AVAILABLE", True),
            patch("appinfra.app.fastapi.runtime.adapter.FastAPI") as mock_fastapi,
            patch("appinfra.app.fastapi.runtime.adapter.CORSMiddleware") as mock_cors,
        ):
            mock_app = MagicMock()
            mock_fastapi.return_value = mock_app
            yield {
                "FastAPI": mock_fastapi,
                "CORSMiddleware": mock_cors,
                "app": mock_app,
            }

    def test_initialization(self, mock_fastapi):
        """Test adapter initialization."""
        config = ApiConfig(title="Test API")
        adapter = FastAPIAdapter(config)

        assert adapter._config is config
        assert adapter._routes == []
        assert adapter._routers == []
        assert adapter._middleware == []
        assert adapter._exception_handlers == []
        assert adapter._cors is None

    def test_add_route(self, mock_fastapi):
        """Test adding a route."""
        adapter = FastAPIAdapter(ApiConfig())
        route = RouteDefinition(path="/test", handler=lambda: None)

        adapter.add_route(route)

        assert len(adapter._routes) == 1
        assert adapter._routes[0] is route

    def test_add_router(self, mock_fastapi):
        """Test adding a router."""
        adapter = FastAPIAdapter(ApiConfig())
        router_def = RouterDefinition(router=MagicMock())

        adapter.add_router(router_def)

        assert len(adapter._routers) == 1
        assert adapter._routers[0] is router_def

    def test_add_middleware(self, mock_fastapi):
        """Test adding middleware."""
        adapter = FastAPIAdapter(ApiConfig())
        mw_def = MiddlewareDefinition(middleware_class=MagicMock)

        adapter.add_middleware(mw_def)

        assert len(adapter._middleware) == 1
        assert adapter._middleware[0] is mw_def

    def test_add_exception_handler(self, mock_fastapi):
        """Test adding exception handler."""
        adapter = FastAPIAdapter(ApiConfig())
        handler_def = ExceptionHandlerDefinition(
            exc_class=ValueError, handler=lambda r, e: None
        )

        adapter.add_exception_handler(handler_def)

        assert len(adapter._exception_handlers) == 1
        assert adapter._exception_handlers[0] is handler_def

    def test_set_cors(self, mock_fastapi):
        """Test setting CORS."""
        adapter = FastAPIAdapter(ApiConfig())
        cors = CORSDefinition(origins=["*"])

        adapter.set_cors(cors)

        assert adapter._cors is cors

    def test_build_creates_app(self, mock_fastapi):
        """Test build creates FastAPI app."""
        config = ApiConfig(title="My API", description="Test", version="1.0.0")
        adapter = FastAPIAdapter(config)

        app = adapter.build()

        mock_fastapi["FastAPI"].assert_called_once_with(
            title="My API", description="Test", version="1.0.0"
        )
        assert app is mock_fastapi["app"]

    def test_build_adds_routes(self, mock_fastapi):
        """Test build adds routes to app."""
        adapter = FastAPIAdapter(ApiConfig())

        handler = lambda: None
        adapter.add_route(
            RouteDefinition(
                path="/test",
                handler=handler,
                methods=["POST"],
                response_model=dict,
                tags=["test"],
            )
        )

        adapter.build()

        mock_fastapi["app"].add_api_route.assert_called_once()

    def test_build_adds_cors(self, mock_fastapi):
        """Test build adds CORS middleware."""
        adapter = FastAPIAdapter(ApiConfig())
        adapter.set_cors(CORSDefinition(origins=["http://localhost:3000"]))

        adapter.build()

        mock_fastapi["app"].add_middleware.assert_called()

    def test_build_with_ipc_channel(self, mock_fastapi):
        """Test build stores IPC channel in app state."""
        adapter = FastAPIAdapter(ApiConfig())
        ipc_channel = MagicMock()

        app = adapter.build(ipc_channel=ipc_channel)

        assert mock_fastapi["app"].state.ipc_channel is ipc_channel

    def test_build_adds_middleware(self, mock_fastapi):
        """Test build adds custom middleware."""

        class CustomMiddleware:
            pass

        adapter = FastAPIAdapter(ApiConfig())
        adapter.add_middleware(MiddlewareDefinition(CustomMiddleware, {"timeout": 30}))

        adapter.build()

        # Check that add_middleware was called with the custom middleware
        calls = mock_fastapi["app"].add_middleware.call_args_list
        # First call might be CORS, find our middleware
        found = False
        for call in calls:
            if call[0][0] is CustomMiddleware:
                found = True
                assert call[1]["timeout"] == 30
        assert found

    def test_build_adds_exception_handlers(self, mock_fastapi):
        """Test build adds exception handlers."""

        def error_handler(request, exc):
            pass

        adapter = FastAPIAdapter(ApiConfig())
        adapter.add_exception_handler(
            ExceptionHandlerDefinition(ValueError, error_handler)
        )

        adapter.build()

        mock_fastapi["app"].add_exception_handler.assert_called()

    def test_build_adds_routers(self, mock_fastapi):
        """Test build adds routers."""
        mock_router = MagicMock()

        adapter = FastAPIAdapter(ApiConfig())
        adapter.add_router(RouterDefinition(mock_router, prefix="/v1", tags=["api"]))

        adapter.build()

        mock_fastapi["app"].include_router.assert_called_once()

    def test_build_adds_health_route_with_ipc(self, mock_fastapi):
        """Test build adds health route when IPC enabled with health reporting."""
        from appinfra.app.fastapi.config.ipc import IPCConfig

        config = ApiConfig(ipc=IPCConfig(enable_health_reporting=True))
        adapter = FastAPIAdapter(config)

        ipc_channel = MagicMock()
        ipc_channel.health_status = {"status": "ok"}

        adapter.build(ipc_channel=ipc_channel)

        # Should have called add_api_route for /_health
        calls = mock_fastapi["app"].add_api_route.call_args_list
        health_call = [c for c in calls if c[0][0] == "/_health"]
        assert len(health_call) == 1
