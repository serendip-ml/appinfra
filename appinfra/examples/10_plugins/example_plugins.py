# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

# ci-run: --help
# ci-run: metrics

"""
Example plugin implementations for the AppBuilder framework.

Each plugin contributes to the app from its ``configure(builder)`` hook:
tools through ``builder.tools``, lifecycle hooks through
``builder.lifecycle``, and routes or middleware through ``builder.server``.
The app declares ``.server`` so the plugins' routes and middleware have a
server to land on; ``serve`` starts it.

Usage:
    python example_plugins.py --help
    python example_plugins.py metrics
    python example_plugins.py serve      # then GET /metrics, GET /api/anything
"""

from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

# Allow running from a source checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from appinfra.app.builder.app import AppBuilder
from appinfra.app.builder.hook import HookBuilder
from appinfra.app.builder.plugin import Plugin
from appinfra.app.builder.tool import ToolBuilder
from appinfra.app.core.app import App

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

# -----------------------------------------------------------------------------
# ASGI middleware
#
# Plain ASGI classes, no framework base class: the server adds middleware with
# ``add_middleware(cls, **options)``, which instantiates ``cls(app, **options)``.
# -----------------------------------------------------------------------------


async def _plain_response(send: Send, status: int, body: bytes) -> None:
    """Send a text/plain response."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BearerAuthMiddleware:
    """Reject ``/api/*`` requests that carry no ``Authorization`` header."""

    def __init__(self, app: Any, auth_type: str = "jwt") -> None:
        self._app = app
        self._auth_type = auth_type

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api"):
            headers = dict(scope.get("headers") or [])
            if b"authorization" not in headers:
                await _plain_response(
                    send, 401, f"{self._auth_type} token required".encode()
                )
                return
        await self._app(scope, receive, send)


class RequestCounterMiddleware:
    """Count requests per path into a dict shared with the metrics plugin."""

    def __init__(self, app: Any, counts: dict[str, int]) -> None:
        self._app = app
        self._counts = counts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope["path"]
            self._counts[path] = self._counts.get(path, 0) + 1
        await self._app(scope, receive, send)


# -----------------------------------------------------------------------------
# Plugins
# -----------------------------------------------------------------------------


class DatabasePlugin(Plugin):
    """Plugin for database functionality: tools plus connect/disconnect hooks."""

    def __init__(self, connection_string: str | None = None):
        super().__init__("database")
        self.connection_string = connection_string
        self._connection = None

    def configure(self, builder: AppBuilder) -> None:
        """Configure database tools and hooks."""
        builder.tools.with_tool_builder(
            ToolBuilder("migrate")
            .with_help("Run database migrations")
            .with_run_function(self._migrate)
        )

        builder.tools.with_tool_builder(
            ToolBuilder("db-status")
            .with_help("Check database status")
            .with_run_function(self._check_status)
        )

        builder.lifecycle.with_hook_builder(
            HookBuilder().on_startup(self._connect_db).on_shutdown(self._disconnect_db)
        )

    def initialize(self, application: App) -> None:
        """Initialize database connection."""
        if self.connection_string:
            # Initialize database connection
            pass

    def cleanup(self, application: App) -> None:
        """Clean up database connection."""
        if self._connection:
            # Close database connection
            pass

    def _migrate(self, tool: Any, **kwargs: Any) -> int:
        """Run database migrations."""
        tool.lg.info("running database migrations...")
        return 0

    def _check_status(self, tool: Any, **kwargs: Any) -> int:
        """Check database status."""
        tool.lg.info("checking database status...")
        return 0

    def _connect_db(self, context: Any) -> None:
        """Connect to database on startup."""
        if self.connection_string:
            # Connect to database
            pass

    def _disconnect_db(self, context: Any) -> None:
        """Disconnect from database on shutdown."""
        if self._connection:
            # Disconnect from database
            pass


class AuthPlugin(Plugin):
    """Plugin for authentication: login/logout tools plus server middleware."""

    def __init__(self, auth_type: str = "jwt"):
        super().__init__("auth")
        self.auth_type = auth_type

    def configure(self, builder: AppBuilder) -> None:
        """Configure authentication tools and middleware."""
        builder.tools.with_tool_builder(
            ToolBuilder("login")
            .with_help("Authenticate user")
            .with_run_function(self._login)
        )

        builder.tools.with_tool_builder(
            ToolBuilder("logout")
            .with_help("Logout user")
            .with_run_function(self._logout)
        )

        # Middleware on the app's HTTP server; the app must declare .server
        builder.server.routes.with_middleware(
            BearerAuthMiddleware, auth_type=self.auth_type
        )

    def _login(self, tool: Any, **kwargs: Any) -> int:
        """Handle user login."""
        tool.lg.info("handling user login...")
        return 0

    def _logout(self, tool: Any, **kwargs: Any) -> int:
        """Handle user logout."""
        tool.lg.info("handling user logout...")
        return 0


class LoggingPlugin(Plugin):
    """Plugin for enhanced logging: a tool plus startup and error hooks."""

    def __init__(self, log_file: str | None = None):
        super().__init__("logging")
        self.log_file = log_file

    def configure(self, builder: AppBuilder) -> None:
        """Configure logging tools and hooks."""
        builder.tools.with_tool_builder(
            ToolBuilder("log-level")
            .with_help("Set log level")
            .with_run_function(self._set_log_level)
        )

        builder.lifecycle.with_hook_builder(
            HookBuilder().on_startup(self._setup_logging).on_error(self._log_error)
        )

    def _set_log_level(self, tool: Any, **kwargs: Any) -> int:
        """Set log level."""
        tool.lg.info("setting log level...")
        return 0

    def _setup_logging(self, context: Any) -> None:
        """Setup enhanced logging on startup."""
        if self.log_file:
            # Setup file logging
            pass

    def _log_error(self, context: Any) -> None:
        """Log errors with enhanced formatting."""
        if context.error:
            # Enhanced error logging
            pass


class MetricsPlugin(Plugin):
    """Plugin for metrics: a tool, a ``/metrics`` route and counting middleware."""

    def __init__(self) -> None:
        super().__init__("metrics")
        self._counts: dict[str, int] = {}

    def configure(self, builder: AppBuilder) -> None:
        """Configure the metrics tool, route and middleware."""
        builder.tools.with_tool_builder(
            ToolBuilder("metrics")
            .with_help("Show application metrics")
            .with_run_function(self._show_metrics)
        )

        # Route and middleware on the app's HTTP server
        builder.server.routes.with_route("/metrics", self._metrics).with_middleware(
            RequestCounterMiddleware, counts=self._counts
        )

    def _metrics(self) -> dict[str, dict[str, int]]:
        """Serve the request counts."""
        return {"requests": dict(self._counts)}

    def _show_metrics(self, tool: Any, **kwargs: Any) -> int:
        """Show application metrics."""
        tool.lg.info("request counts", extra={"requests": dict(self._counts)})
        return 0


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    """Build an app whose tools, hooks, routes and middleware come from plugins."""
    app = (
        AppBuilder("plugins-demo")
        .with_description("Tools, hooks, routes and middleware contributed by plugins")
        .cli(log_level=True)
        .server(port=8090, title="Plugins demo")
        .tools(
            plugins=[
                DatabasePlugin(connection_string="postgresql://localhost/demo"),
                AuthPlugin(auth_type="jwt"),
                LoggingPlugin(),
                MetricsPlugin(),
            ]
        )
        .build()
    )
    return app.main()


if __name__ == "__main__":
    sys.exit(main())
