# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""ServerPlugin for AppBuilder integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..builder.plugin import Plugin
from ..tools.base import Tool, ToolConfig
from .builder.server import ServerBuilder
from .runtime.server import Server

if TYPE_CHECKING:
    from ..builder.app import AppBuilder
    from ..core.app import App

logger = logging.getLogger("fastapi.plugin")


class ServeTool(Tool):
    """
    Tool that starts the HTTP server.

    Registered by ServerPlugin to add a "serve" command to CLI apps.
    """

    def __init__(
        self,
        server: Server,
        name: str = "serve",
        help_text: str = "Start the HTTP server",
    ) -> None:
        """
        Initialize serve tool.

        Args:
            server: Server instance to start
            name: Tool name (default: "serve")
            help_text: Help text for CLI
        """
        config = ToolConfig(
            name=name,
            aliases=[],
            help_text=help_text,
            description=f"Start the {server.name} HTTP server",
        )
        super().__init__(parent=None, config=config)
        self._server = server

    def _create_config(self) -> ToolConfig:
        """Create default config (called if config not provided)."""
        return ToolConfig(
            name="serve",
            aliases=[],
            help_text="Start the HTTP server",
        )

    def run(self, **kwargs: Any) -> int:
        """
        Run the HTTP server.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        self.lg.info(
            "starting server...",
            extra={"host": self._server.config.host, "port": self._server.config.port},
        )

        try:
            self._server.start()
            return 0
        except KeyboardInterrupt:
            self.lg.info("server interrupted by user")
            self._server.stop()
            return 130  # Standard exit code for SIGINT
        except Exception as e:
            self.lg.error("server error", extra={"exception": e})
            self._server.stop()
            return 1


class ServerPlugin(Plugin):
    """
    Plugin to integrate FastAPI server with AppBuilder CLI apps.

    Allows CLI applications to also serve HTTP by adding a "serve" tool
    that starts the configured server.

    Given a ``ServerBuilder`` instead of a built ``Server``, the plugin builds
    the server when it is configured, after plugins registered earlier have
    added their routes and middleware. ``AppBuilder.server`` registers the
    plugin this way.

    Example:
        server = (ServerBuilder("myapi")
            .with_port(8000)
            .routes.with_route("/health", health).done()
            .build())

        app = (AppBuilder("myapp")
            .tools.with_plugin(ServerPlugin(server)).done()
            .build())

        # CLI: myapp serve
    """

    def __init__(
        self,
        server: Server | ServerBuilder,
        tool_name: str = "serve",
        tool_help: str = "Start the HTTP server",
    ) -> None:
        """
        Initialize plugin.

        Args:
            server: Configured Server instance, or a ServerBuilder to build
                when the plugin is configured
            tool_name: Name for the serve command (default: "serve")
            tool_help: Help text for the serve command
        """
        super().__init__(name="ServerPlugin")
        self._server: Server | ServerBuilder = server
        self._tool_name = tool_name
        self._tool_help = tool_help
        self._tool: ServeTool | None = None

    def configure(self, builder: AppBuilder) -> None:
        """
        Build the server if given a builder, and register the serve tool.

        Called during AppBuilder.build() phase.
        """
        if isinstance(self._server, ServerBuilder):
            # The AppBuilder server scope overrides build() to raise; the base
            # implementation is the real one.
            self._server = ServerBuilder.build(self._server)
        self._tool = ServeTool(
            server=self._server,
            name=self._tool_name,
            help_text=self._tool_help,
        )
        # Add tool to builder's tool list
        builder._tools.append(self._tool)

    def initialize(self, application: App) -> None:
        """
        Initialize plugin with the application.

        Called after App is fully constructed.
        """
        # Set the tool's parent to the app for proper logging chain
        if self._tool is not None:
            self._tool.set_parent(application)

    def cleanup(self, application: App) -> None:
        """
        Stop server on app shutdown.

        Called during app shutdown phase.
        """
        if isinstance(self._server, ServerBuilder):
            return  # never configured, nothing was started
        if self._server.is_running:
            logger.info("stopping server...")
            self._server.stop()
