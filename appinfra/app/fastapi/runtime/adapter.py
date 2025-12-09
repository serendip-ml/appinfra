"""FastAPI application adapter."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..config.api import ApiConfig

if TYPE_CHECKING:
    from .ipc import IPCChannel

logger = logging.getLogger("fastapi.adapter")

# Guard FastAPI imports for optional dependency
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.routing import APIRouter

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = Any  # type: ignore[assignment,misc]
    CORSMiddleware = Any  # type: ignore[assignment,misc]
    APIRouter = Any  # type: ignore[assignment,misc]


@dataclass
class RouteDefinition:
    """Definition for a route to register."""

    path: str
    handler: Callable[..., Any]
    methods: list[str] = field(default_factory=lambda: ["GET"])
    response_model: type[Any] | None = None
    tags: list[str] | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterDefinition:
    """Definition for a router to include."""

    router: Any  # APIRouter
    prefix: str = ""
    tags: list[str] | None = None


@dataclass
class MiddlewareDefinition:
    """Definition for middleware to add."""

    middleware_class: type[Any]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class CORSDefinition:
    """Definition for CORS configuration."""

    origins: list[str]
    allow_credentials: bool = False
    allow_methods: list[str] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class ExceptionHandlerDefinition:
    """Definition for exception handler."""

    exc_class: type[Exception]
    handler: Callable[..., Any]


class FastAPIAdapter:
    """
    Adapter for constructing FastAPI applications.

    Collects route/middleware definitions during build phase,
    then constructs the FastAPI app when build() is called.

    This separation allows the builder to collect configuration
    before FastAPI is imported (important for subprocess isolation
    where FastAPI should be imported inside the subprocess).
    """

    def __init__(self, config: ApiConfig) -> None:
        """
        Initialize adapter.

        Args:
            config: API configuration

        Raises:
            ImportError: If FastAPI is not installed
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError(
                "FastAPI is not installed. Install with: pip install appinfra[fastapi]"
            )

        self._config = config
        self._routes: list[RouteDefinition] = []
        self._routers: list[RouterDefinition] = []
        self._middleware: list[MiddlewareDefinition] = []
        self._exception_handlers: list[ExceptionHandlerDefinition] = []
        self._cors: CORSDefinition | None = None

    def add_route(self, route: RouteDefinition) -> None:
        """Add a route definition."""
        self._routes.append(route)

    def add_router(self, router: RouterDefinition) -> None:
        """Add a router definition."""
        self._routers.append(router)

    def add_middleware(self, middleware: MiddlewareDefinition) -> None:
        """Add a middleware definition."""
        self._middleware.append(middleware)

    def add_exception_handler(self, handler: ExceptionHandlerDefinition) -> None:
        """Add an exception handler definition."""
        self._exception_handlers.append(handler)

    def set_cors(self, cors: CORSDefinition) -> None:
        """Set CORS configuration."""
        self._cors = cors

    def build(self, ipc_channel: IPCChannel | None = None) -> FastAPI:
        """
        Build the FastAPI application.

        Args:
            ipc_channel: Optional IPCChannel to store in app.state.
                When provided, enables IPC-based route handlers and
                health reporting (if configured).

        Returns:
            Configured FastAPI application
        """
        app = FastAPI(
            title=self._config.title,
            description=self._config.description,
            version=self._config.version,
        )

        # Store IPC channel in app state for dependency injection
        if ipc_channel is not None:
            app.state.ipc_channel = ipc_channel

        self._configure_middleware(app)
        self._configure_exception_handlers(app)
        self._configure_routes(app)
        self._configure_routers(app)

        # Add built-in health route if IPC enabled and configured
        if (
            ipc_channel is not None
            and self._config.ipc
            and self._config.ipc.enable_health_reporting
        ):
            self._add_health_route(app, ipc_channel)

        return app

    def _configure_middleware(self, app: FastAPI) -> None:
        """Configure middleware on the app."""
        # Add CORS middleware first (order matters for middleware)
        if self._cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self._cors.origins,
                allow_credentials=self._cors.allow_credentials,
                allow_methods=self._cors.allow_methods,
                allow_headers=self._cors.allow_headers,
            )

        # Add other middleware
        for mw in self._middleware:
            app.add_middleware(mw.middleware_class, **mw.options)  # type: ignore[arg-type]

    def _configure_exception_handlers(self, app: FastAPI) -> None:
        """Configure exception handlers on the app."""
        for handler in self._exception_handlers:
            app.add_exception_handler(handler.exc_class, handler.handler)

    def _configure_routes(self, app: FastAPI) -> None:
        """Configure individual routes on the app."""
        for route in self._routes:
            app.add_api_route(
                route.path,
                route.handler,
                methods=route.methods,
                response_model=route.response_model,
                tags=route.tags,  # type: ignore[arg-type]
                **route.kwargs,
            )

    def _configure_routers(self, app: FastAPI) -> None:
        """Configure routers on the app."""
        for router_def in self._routers:
            app.include_router(
                router_def.router,
                prefix=router_def.prefix,
                tags=router_def.tags,  # type: ignore[arg-type]
            )

    def _add_health_route(self, app: FastAPI, ipc_channel: IPCChannel) -> None:
        """
        Add built-in health check route.

        Reports server status and IPC health metrics.
        """

        async def health() -> dict[str, Any]:
            return {
                "status": "ok",
                "ipc": ipc_channel.health_status,
            }

        app.add_api_route(
            "/_health",
            health,
            methods=["GET"],
            tags=["Health"],
            summary="Health check with IPC status",
        )
