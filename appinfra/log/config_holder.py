"""
Thread-safe configuration holder for hot-reload support.

This module provides a wrapper around LogConfig that allows atomic updates
while maintaining thread-safety. Used by formatters to access configuration
indirectly, enabling hot-reload without replacing formatter instances.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import LogConfig


class LogConfigHolder:
    """
    Thread-safe holder for LogConfig that supports atomic updates.

    Used by formatters to access configuration indirectly, allowing
    hot-reload without replacing formatter instances.

    Example:
        >>> from appinfra.log.config import LogConfig
        >>> config = LogConfig.from_params("info")
        >>> holder = LogConfigHolder(config)
        >>> holder.level  # Access via property
        20
        >>> new_config = LogConfig.from_params("debug")
        >>> holder.update(new_config)  # Atomic update
        >>> holder.level
        10
    """

    def __init__(self, config: LogConfig) -> None:
        """
        Initialize the holder with a LogConfig.

        Args:
            config: Initial LogConfig instance
        """
        self._config = config
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[LogConfig], None]] = []

    @property
    def config(self) -> LogConfig:
        """Get current config (thread-safe read)."""
        with self._lock:
            return self._config

    # Delegate properties for convenient access

    @property
    def level(self) -> int | bool:
        """Get current log level."""
        return self.config.level

    @property
    def location(self) -> int:
        """Get current location display depth."""
        return self.config.location

    @property
    def micros(self) -> bool:
        """Get whether microsecond precision is enabled."""
        return self.config.micros

    @property
    def colors(self) -> bool:
        """Get whether colored output is enabled."""
        return self.config.colors

    @property
    def location_color(self) -> str | None:
        """Get current location color."""
        return self.config.location_color

    def update(self, new_config: LogConfig) -> None:
        """
        Update config atomically (thread-safe write).

        Args:
            new_config: New LogConfig to replace current config

        Note:
            Callbacks are invoked outside the lock to prevent deadlocks.
        """
        with self._lock:
            self._config = new_config
            callbacks = list(self._callbacks)

        # Notify listeners outside lock to avoid deadlock
        for callback in callbacks:
            try:
                callback(new_config)
            except Exception:
                pass  # Don't let callback errors break update

    def add_update_callback(self, callback: Callable[[LogConfig], None]) -> None:
        """
        Register callback for config updates.

        Args:
            callback: Function to call when config is updated.
                     Receives the new LogConfig as argument.
        """
        with self._lock:
            self._callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[LogConfig], None]) -> None:
        """
        Remove a previously registered callback.

        Args:
            callback: Callback function to remove
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass  # Callback not found, ignore
