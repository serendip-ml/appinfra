"""
Application lifecycle management.

This module provides lifecycle management for the application framework.
"""

import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ... import time
from ...log import LoggerFactory
from ...log.handler_factory import HandlerRegistry
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
        self._handler_registry: HandlerRegistry | None = None
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
        from typing import cast

        from .logging_utils import setup_logging_from_config

        # Use setup_logging_from_config to properly handle handlers config
        logger, self._handler_registry = setup_logging_from_config(config)
        self._logger = cast("Logger", logger)

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

        # Start hot-reload watcher if configured
        self._start_hot_reload_watcher(config)

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

    def _get_hot_reload_config(self, config: Any) -> Any | None:
        """Extract hot-reload config from logging section if enabled."""
        if not hasattr(config, "logging"):
            return None

        hot_reload_config = getattr(config.logging, "hot_reload", None)
        if hot_reload_config is None:
            return None

        enabled = getattr(hot_reload_config, "enabled", False)
        return hot_reload_config if enabled else None

    def _resolve_hot_reload_config_path(self, hot_reload_config: Any) -> str | None:
        """Resolve config path from hot_reload config or application."""
        config_path = getattr(hot_reload_config, "config_path", None)
        if config_path is None and hasattr(self.application, "_config_path"):
            config_path = self.application._config_path
        return config_path

    def _start_hot_reload_watcher(self, config: Any) -> None:
        """Start config file watcher if hot-reload is enabled."""
        hot_reload_config = self._get_hot_reload_config(config)
        if hot_reload_config is None:
            return

        config_path = self._resolve_hot_reload_config_path(hot_reload_config)
        if config_path is None:
            if self._lifecycle_logger:
                self._lifecycle_logger.warning(
                    "hot-reload enabled but no config path available"
                )
            return

        self._configure_and_start_watcher(hot_reload_config, config_path)

    def _configure_and_start_watcher(
        self, hot_reload_config: Any, config_path: str
    ) -> None:
        """Configure and start the hot-reload watcher."""
        try:
            from appinfra.log.watcher import LogConfigWatcher

            section = getattr(hot_reload_config, "section", "logging")
            debounce_ms = getattr(hot_reload_config, "debounce_ms", 500)

            watcher = LogConfigWatcher.get_instance()
            watcher.configure(config_path, section=section, debounce_ms=debounce_ms)
            watcher.start()

            if self._lifecycle_logger:
                self._lifecycle_logger.debug(
                    "hot-reload watcher started",
                    extra={"config_path": str(config_path)},
                )
        except ImportError:
            if self._lifecycle_logger:
                self._lifecycle_logger.warning(
                    "hot-reload enabled but watchdog not installed. "
                    "Install with: pip install appinfra[hotreload]"
                )
        except Exception as e:
            if self._lifecycle_logger:
                self._lifecycle_logger.error(
                    "failed to start hot-reload watcher", extra={"exception": e}
                )

    def _stop_hot_reload_watcher(self) -> None:
        """Stop config file watcher if running."""
        try:
            from appinfra.log.watcher import LogConfigWatcher

            watcher = LogConfigWatcher.get_instance()
            if watcher.is_running():
                watcher.stop()
                if self._lifecycle_logger:
                    self._lifecycle_logger.debug("hot-reload watcher stopped")
        except ImportError:
            pass  # watchdog not installed, nothing to stop
        except Exception as e:
            if self._lifecycle_logger:
                self._lifecycle_logger.error(
                    "failed to stop hot-reload watcher",
                    extra={"exception": e},
                )

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

        # Stop hot-reload watcher first (not in a timed phase)
        self._stop_hot_reload_watcher()

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
