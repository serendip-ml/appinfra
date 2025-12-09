"""
Shutdown manager for handling application shutdown signals and coordination.

This module provides centralized shutdown signal handling for graceful
application termination on SIGTERM and SIGINT signals.
"""

import logging
import signal
import sys
from collections.abc import Callable
from typing import Any


class ShutdownManager:
    """Manages application shutdown signals and coordination."""

    def __init__(
        self,
        shutdown_callback: Callable[[int], int],
        timeout: float = 30.0,
        logger: Any | None = None,
        start_time: float | None = None,
    ):
        """
        Initialize shutdown manager.

        Args:
            shutdown_callback: Function to call on shutdown (typically lifecycle.shutdown)
            timeout: Global shutdown timeout in seconds
            logger: Logger instance for final "done" message
            start_time: Application start time for elapsed time calculation
        """
        self._shutdown_callback = shutdown_callback
        self._timeout = timeout
        self._logger = logger
        self._start_time = start_time
        self._shutting_down = False
        from typing import Any

        self._original_handlers: dict[signal.Signals, Any] = {}

    def register_signal_handlers(self) -> None:
        """Register signal handlers for SIGTERM and SIGINT."""
        self._original_handlers[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, self._handle_signal
        )
        self._original_handlers[signal.SIGINT] = signal.signal(
            signal.SIGINT, self._handle_signal
        )

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """
        Handle shutdown signal.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        if self._shutting_down:
            # Already shutting down, ignore duplicate signals
            return

        self._shutting_down = True

        # Determine return code based on signal
        return_code = 130 if signum == signal.SIGINT else 143  # 143 = SIGTERM

        # Call shutdown callback
        try:
            # Perform shutdown (hooks, plugins, databases, log handlers)
            final_code = self._shutdown_callback(return_code)
            sys.exit(final_code)
        except Exception as e:
            logging.error(f"Shutdown failed: {e}")
            sys.exit(1)

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutting_down
