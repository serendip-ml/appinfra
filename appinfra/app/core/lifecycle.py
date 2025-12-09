"""
Application lifecycle management.

This module provides lifecycle management for the application framework.
"""

import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ... import time
from ...log import LogConfig, LoggerFactory
from ..errors import LifecycleError
from ..tools.base import Tool

if TYPE_CHECKING:
    from ...log.logger import Logger
    from .shutdown import ShutdownManager


class LifecycleManager:
    """Manages application lifecycle operations."""

    def __init__(self, application: Any):
        self.application = application
        self._logger: Logger | None = (
            None  # Root logger at / (shared with App, passed to user tools)
        )
        self._infra_logger: Logger | None = (
            None  # Framework logger at /infra (passed to framework components)
        )
        self._lifecycle_logger: Logger | None = (
            None  # Derived logger for lifecycle messages at /infra/app/lifecycle
        )
        self._start_time: float | None = None

        # Component registrations for shutdown
        self._hook_manager = None
        self._plugin_manager = None
        self._db_manager = None
        self._db_handlers: list[Any] = []

        # Shutdown coordination
        self._shutdown_manager: ShutdownManager | None = None
        self._shutdown_timeouts = {
            "hooks": 5.0,
            "plugins": 10.0,
            "databases": 10.0,
            "logging": 5.0,
        }

    def _setup_loggers(self, config: Any) -> None:
        """Create and configure logger hierarchy."""
        log_level, log_location, log_micros, log_location_color = (
            self._extract_logging_config(config)
        )
        log_location_color = self._resolve_color_name(log_location_color)

        log_config = LogConfig.from_params(
            log_level,
            location=log_location,
            micros=log_micros,
            location_color=log_location_color,
        )

        # Create root logger at / for user tools
        self._logger = LoggerFactory.create("/", log_config)
        self._logger.debug(
            "*** start ***", extra={"prog_args": " ".join(sys.argv), "cwd": os.getcwd()}
        )

        # Create /infra logger for framework components
        self._infra_logger = LoggerFactory.derive(self._logger, "infra")

        # Create lifecycle internal logger at /infra/app/lifecycle
        self._lifecycle_logger = LoggerFactory.derive(
            self._infra_logger, ["app", "lifecycle"]
        )

    def initialize(self, config: Any) -> None:
        """Initialize the lifecycle manager."""
        self._start_time = time.start()

        # Setup logger hierarchy
        self._setup_loggers(config)

        # Load shutdown timeouts and create shutdown manager
        if hasattr(config, "shutdown_timeouts"):
            self._shutdown_timeouts.update(config.shutdown_timeouts)

        self._create_shutdown_manager(config)

    def _extract_logging_config(self, config: Any) -> tuple[Any, Any, bool, Any]:
        """
        Extract logging configuration from config object.

        Returns:
            Tuple of (log_level, log_location, log_micros, log_location_color)
        """
        # Check if we're in a test environment and use test logging level if so
        if os.getenv("INFRA_TEST_LOGGING_LEVEL") is not None:
            log_level = os.getenv("INFRA_TEST_LOGGING_LEVEL")
        else:
            log_level = (
                getattr(config.logging, "level", "info")
                if hasattr(config, "logging")
                else "info"
            )

        log_location = (
            getattr(config.logging, "location", 0) if hasattr(config, "logging") else 0
        )
        log_micros = (
            getattr(config.logging, "micros", False)
            if hasattr(config, "logging")
            else False
        )
        log_location_color = (
            getattr(config.logging, "location_color", None)
            if hasattr(config, "logging")
            else None
        )

        return log_level, log_location, log_micros, log_location_color

    def _resolve_color_name(self, color_value: Any) -> Any:
        """
        Convert color name to ANSI code if it's a string.

        Args:
            color_value: Color value (string name or ANSI code)

        Returns:
            Resolved ANSI code or original value
        """
        if isinstance(color_value, str):
            from appinfra.log.colors import ColorManager

            resolved_color = ColorManager.from_name(color_value)
            if resolved_color is not None:
                return resolved_color
            # If from_name returns None, keep the original string
            # (might be a direct ANSI code for backwards compatibility)
        return color_value

    def _create_shutdown_manager(self, config: Any) -> None:
        """Create and register shutdown manager."""
        from .shutdown import ShutdownManager

        shutdown_timeout = getattr(config, "shutdown_timeout", 30.0)
        self._shutdown_manager = ShutdownManager(
            self.shutdown,
            shutdown_timeout,
            logger=self._logger,
            start_time=self._start_time,
        )
        self._shutdown_manager.register_signal_handlers()

    def setup_tool(self, tool: Tool, **kwargs: Any) -> None:
        """Set up a tool for execution."""
        if not self._logger:
            raise LifecycleError("Lifecycle manager not initialized")

        assert self._lifecycle_logger is not None  # Set during initialization

        start_t = time.start()
        self._lifecycle_logger.trace("setting up tool...", extra={"tool": tool.name})

        try:
            tool.setup(**kwargs)
            self._lifecycle_logger.debug(
                "tool setup complete",
                extra={"after": time.since(start_t), "tool": tool.name},
            )
        except Exception as e:
            self._lifecycle_logger.error(
                "tool setup failed",
                extra={
                    "after": time.since(start_t),
                    "tool": tool.name,
                    "error": str(e),
                },
            )
            raise LifecycleError(f"Failed to setup tool '{tool.name}': {e}") from e

    def execute_tool(self, tool: Tool, **kwargs: Any) -> int:
        """Execute a tool."""
        if not self._logger:
            raise LifecycleError("Lifecycle manager not initialized")

        assert self._lifecycle_logger is not None  # Set during initialization

        self._lifecycle_logger.debug(
            "running tool",
            extra={
                "after": time.since(self._start_time) if self._start_time else 0.0,
                "tool": tool.name,
            },
        )

        try:
            # Pass args to the tool if provided
            if "args" in kwargs:
                tool._parsed_args = kwargs["args"]  # type: ignore[attr-defined]
            return tool.run(**kwargs)
        except Exception as e:
            self._lifecycle_logger.error(
                "tool execution failed",
                extra={"tool": tool.name, "error": str(e)},
            )
            raise LifecycleError(f"Tool '{tool.name}' execution failed: {e}") from e

    def register_hook_manager(self, hook_manager: Any) -> None:
        """Register hook manager for shutdown."""
        self._hook_manager = hook_manager

    def register_plugin_manager(self, plugin_manager: Any) -> None:
        """Register plugin manager for shutdown."""
        self._plugin_manager = plugin_manager

    def register_db_manager(self, db_manager: Any) -> None:
        """Register database manager for shutdown."""
        self._db_manager = db_manager

    def register_db_handler(self, handler: Any) -> None:
        """Register database logging handler for shutdown."""
        if handler not in self._db_handlers:
            self._db_handlers.append(handler)

    def shutdown(self, return_code: int = 0) -> int:
        """
        Orchestrate graceful shutdown of all components.

        Args:
            return_code: Exit code for the application

        Returns:
            Final return code after cleanup
        """
        if not self._logger:
            return return_code

        assert self._lifecycle_logger is not None  # Set during initialization

        self._lifecycle_logger.debug("shutting down...")

        # Execute shutdown phases
        self._execute_phase("hooks", self._shutdown_hooks)
        self._execute_phase("plugins", self._shutdown_plugins)
        self._execute_phase("databases", self._shutdown_databases)
        self._execute_phase("logging", self._shutdown_log_handlers)

        # Finalize and log completion
        self.finalize(return_code)
        self._log_shutdown_complete(return_code)

        return return_code

    def _log_shutdown_complete(self, return_code: int) -> None:
        """Log shutdown completion with elapsed time."""
        assert self._lifecycle_logger is not None
        self._lifecycle_logger.debug(
            "done",
            extra={
                "after": time.since(self._start_time) if self._start_time else 0.0,
                "return": return_code,
            },
        )

    def _execute_phase(self, phase_name: str, phase_func: Callable[[], None]) -> None:
        """
        Execute a shutdown phase with timeout protection.

        Args:
            phase_name: Name of the phase for logging
            phase_func: Function to execute for this phase
        """
        import signal

        assert (
            self._lifecycle_logger is not None
        )  # Only called from shutdown after init check

        timeout = self._shutdown_timeouts.get(phase_name, 5.0)

        def timeout_handler(signum: int, frame: Any) -> None:
            raise TimeoutError(
                f"Shutdown phase '{phase_name}' exceeded timeout of {timeout}s"
            )

        # Set alarm for timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            phase_func()
        except TimeoutError as e:
            self._lifecycle_logger.warning(f"shutdown timeout: {e}")
        except Exception as e:
            self._lifecycle_logger.error(f"shutdown phase '{phase_name}' failed: {e}")
        finally:
            # Cancel alarm and restore handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def _shutdown_hooks(self) -> None:
        """Trigger shutdown hooks."""
        if not self._hook_manager:
            return

        if self._hook_manager.has_hooks("shutdown"):
            self._lifecycle_logger.trace("triggering shutdown hooks...")
            try:
                from ..builder.hook import HookContext

                context = HookContext(application=self.application)
                self._hook_manager.trigger_hook("shutdown", context)
                self._lifecycle_logger.debug("shutdown hooks completed")
            except Exception as e:
                self._lifecycle_logger.error(
                    "shutdown hooks failed", extra={"exception": e}
                )

    def _shutdown_plugins(self) -> None:
        """Clean up all initialized plugins."""
        if not self._plugin_manager:
            return

        # Skip logging if no plugins were initialized
        if not self._plugin_manager._initialized_plugins:
            return

        self._lifecycle_logger.debug("cleaning up plugins...")
        try:
            self._plugin_manager.cleanup_all(self.application)
            self._lifecycle_logger.debug("plugin cleanup completed")
        except Exception as e:
            self._lifecycle_logger.error(
                "plugin cleanup failed", extra={"exception": e}
            )

    def _shutdown_databases(self) -> None:
        """Close all database connections."""
        if not self._db_manager:
            return

        assert (
            self._lifecycle_logger is not None
        )  # Only called from shutdown after init check

        self._lifecycle_logger.debug("closing database connections...")
        try:
            self._db_manager.close_all()
            self._lifecycle_logger.debug("database connections closed")
        except Exception as e:
            self._lifecycle_logger.error(
                "database shutdown failed", extra={"exception": e}
            )

    def _shutdown_log_handlers(self) -> None:
        """Flush all registered database logging handlers."""
        if not self._db_handlers:
            return

        assert (
            self._lifecycle_logger is not None
        )  # Only called from shutdown after init check

        self._lifecycle_logger.debug("flushing log handlers...")
        for handler in self._db_handlers:
            try:
                handler._flush_batch()
            except Exception as e:
                self._lifecycle_logger.error(
                    "log handler flush failed", extra={"exception": e}
                )
        self._lifecycle_logger.debug("log handlers flushed")

    def finalize(self, return_code: int) -> None:
        """
        Finalize the application lifecycle.

        This method is called after all shutdown phases complete, before the
        final "done" message is logged.
        """
        # Reserved for future finalization logic if needed
        pass

    @property
    def logger(self) -> "Logger | None":
        """Get the root logger (for user tools)."""
        return self._logger

    @property
    def infra_logger(self) -> "Logger | None":
        """Get the infra framework logger (for framework components)."""
        return self._infra_logger
