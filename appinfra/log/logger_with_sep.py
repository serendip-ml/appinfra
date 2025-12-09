"""
Logger with automatic content separators for multiprocessing environments.

This module provides the LoggerWithSeparator class that automatically inserts
separator lines when there's a gap in logging activity, useful for distinguishing
between different processes or time periods in multiprocessing applications.
"""

import multiprocessing
import time
from typing import Any

from . import logger


class LoggerWithSeparator(logger.Logger):
    """
    Logger with automatic content separators for multiprocessing environments.

    This logger automatically inserts separator lines when there's a gap
    in logging activity, useful for distinguishing between different processes
    or time periods in multiprocessing applications.
    """

    # Multiprocessing shared state
    lock = multiprocessing.Lock()
    last_ts = multiprocessing.Value("f", 0)
    new_content_separator_secs = multiprocessing.Value("f", 5.0)

    def _log(self, level: int, msg: str, args: tuple, **kwargs: Any) -> None:  # type: ignore[override]
        """Enhanced logging with separator checking."""
        if self.isEnabledFor(level):
            self._check_separator()
        super()._log(level, msg, args, **kwargs)

    def _check_separator(self) -> None:
        """Check if a separator should be shown."""
        trigger = False

        with LoggerWithSeparator.lock:
            secs = LoggerWithSeparator.new_content_separator_secs.value
            if secs > 0:
                now = time.monotonic()
                last = LoggerWithSeparator.last_ts.value
                LoggerWithSeparator.last_ts.value = now
                trigger = last > 0 and now - last >= secs

        if trigger:
            import logging as stdlib_logging

            from .. import time as infratime

            # Bypass the _log override to avoid recursion
            logger.Logger._log(
                self,
                stdlib_logging.INFO,
                "⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼⎼",
                (),
                extra={
                    "after": infratime.delta.delta_str(now - last, precise=self.micros)
                },
            )

    @staticmethod
    def set_content_separator_secs(secs: float) -> None:
        """
        Set the separator interval in seconds.

        Args:
            secs: Seconds between separators (0 to disable)
        """
        with LoggerWithSeparator.lock:
            LoggerWithSeparator.new_content_separator_secs.value = float(secs)
