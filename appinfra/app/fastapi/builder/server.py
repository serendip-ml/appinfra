"""Main ServerBuilder for FastAPI servers."""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

from ..config.api import ApiConfig
from ..config.ipc import IPCConfig
from ..config.uvicorn import UvicornConfig
from ..runtime.adapter import (
    CORSDefinition,
    ExceptionHandlerDefinition,
    FastAPIAdapter,
    MiddlewareDefinition,
    RouteDefinition,
    RouterDefinition,
)
from ..runtime.server import Server
from .route import RouteConfigurer
from .subprocess import SubprocessConfigurer
from .uvicorn import UvicornConfigurer


class ServerBuilder:
    """
    Fluent builder for FastAPI servers with optional subprocess isolation.

    Follows appinfra.app.AppBuilder patterns:
    - Method chaining with with_*() methods
    - Focused configurers accessed via properties (.routes, .subprocess, .uvicorn)
    - .done() returns to parent builder
    - .build() creates runtime instance

    Example (simple server):
        server = (ServerBuilder("myapi")
            .with_port(8000)
            .routes
                .with_route("/health", health_handler)
                .with_cors(origins=["*"])
                .done()
            .build())

        server.start()  # Blocking

    Example (subprocess mode with IPC):
        request_q, response_q = mp.Queue(), mp.Queue()

        server = (ServerBuilder("worker-api")
            .with_port(8000)
            .routes
                .with_route("/process", process_handler, methods=["POST"])
                .done()
            .subprocess
                .with_ipc(request_q, response_q)
                .with_auto_restart(enabled=True, max_restarts=10)
                .done()
            .uvicorn
                .with_workers(4)
                .done()
            .build())

        proc = server.start_subprocess()  # Non-blocking

        # Main process handles requests via queues
        while True:
            request = request_q.get()
            result = process(request)
            response_q.put(result)
    """

    def __init__(self, name: str) -> None:
        """
        Initialize builder.

        Args:
            name: Server name (used for logging)
        """
        self._name = name

        # Direct config
        self._host = "0.0.0.0"
        self._port = 8000
        self._title = "API Server"
        self._description = ""
        self._version = "0.1.0"
        self._response_timeout = 60.0

        # Subprocess config
        self._request_q: mp.Queue[Any] | None = None
        self._response_q: mp.Queue[Any] | None = None
        self._ipc_config: IPCConfig | None = None
        self._log_file: str | None = None
        self._auto_restart = True
        self._restart_delay = 1.0
        self._max_restarts = 5

        # Uvicorn config
        self._uvicorn_config = UvicornConfig()

        # Routes and middleware
        self._routes: list[RouteDefinition] = []
        self._routers: list[RouterDefinition] = []
        self._middleware: list[MiddlewareDefinition] = []
        self._exception_handlers: list[ExceptionHandlerDefinition] = []
        self._cors: CORSDefinition | None = None

    # Direct configuration methods

    def with_host(self, host: str) -> ServerBuilder:
        """Set the bind address (default: "0.0.0.0")."""
        self._host = host
        return self

    def with_port(self, port: int) -> ServerBuilder:
        """Set the bind port (default: 8000)."""
        self._port = port
        return self

    def with_title(self, title: str) -> ServerBuilder:
        """Set API title for OpenAPI docs."""
        self._title = title
        return self

    def with_description(self, description: str) -> ServerBuilder:
        """Set API description for OpenAPI docs."""
        self._description = description
        return self

    def with_version(self, version: str) -> ServerBuilder:
        """Set API version."""
        self._version = version
        return self

    def with_timeout(self, timeout: float) -> ServerBuilder:
        """Set default response timeout in seconds."""
        self._response_timeout = timeout
        return self

    def with_config(self, config: ApiConfig) -> ServerBuilder:
        """
        Set entire API configuration at once.

        Useful when loading config from file or environment.
        """
        self._host = config.host
        self._port = config.port
        self._title = config.title
        self._description = config.description
        self._version = config.version
        self._response_timeout = config.response_timeout
        self._log_file = config.log_file
        self._auto_restart = config.auto_restart
        self._restart_delay = config.restart_delay
        self._max_restarts = config.max_restarts
        self._uvicorn_config = config.uvicorn

        if config.ipc:
            self._ipc_config = config.ipc

        return self

    # Focused configurers

    @property
    def routes(self) -> RouteConfigurer:
        """Access route and middleware configuration."""
        return RouteConfigurer(self)

    @property
    def subprocess(self) -> SubprocessConfigurer:
        """Access subprocess and IPC configuration."""
        return SubprocessConfigurer(self)

    @property
    def uvicorn(self) -> UvicornConfigurer:
        """Access Uvicorn configuration."""
        return UvicornConfigurer(self)

    # Build

    def _build_config(self) -> ApiConfig:
        """Build API configuration from builder state."""
        return ApiConfig(
            host=self._host,
            port=self._port,
            title=self._title,
            description=self._description,
            version=self._version,
            response_timeout=self._response_timeout,
            log_file=self._log_file,
            auto_restart=self._auto_restart,
            restart_delay=self._restart_delay,
            max_restarts=self._max_restarts,
            uvicorn=self._uvicorn_config,
            ipc=self._ipc_config,
        )

    def _configure_adapter(self, adapter: FastAPIAdapter) -> None:
        """Configure adapter with routes, middleware, and handlers."""
        for route in self._routes:
            adapter.add_route(route)
        for router in self._routers:
            adapter.add_router(router)
        for mw in self._middleware:
            adapter.add_middleware(mw)
        for handler in self._exception_handlers:
            adapter.add_exception_handler(handler)
        if self._cors:
            adapter.set_cors(self._cors)

    def build(self) -> Server:
        """
        Build the Server runtime instance.

        Returns:
            Configured Server ready to start
        """
        config = self._build_config()
        adapter = FastAPIAdapter(config)
        self._configure_adapter(adapter)

        return Server(
            name=self._name,
            config=config,
            adapter=adapter,
            request_q=self._request_q,
            response_q=self._response_q,
        )
