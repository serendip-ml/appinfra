"""
Global registry for LogConfigHolder instances.

This module provides a singleton registry that tracks all active LogConfigHolder
instances, enabling bulk updates when logging configuration changes during hot-reload.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import LogConfig
    from .config_holder import LogConfigHolder


class LogConfigRegistry:
    """
    Singleton registry tracking all active LogConfigHolders.

    Enables bulk updates when configuration changes, propagating
    new settings to all registered formatters/handlers.

    Example:
        >>> registry = LogConfigRegistry.get_instance()
        >>> holder = registry.create_holder(some_config)
        >>> # Later, on config file change:
        >>> registry.update_all(new_config)
    """

    _instance: LogConfigRegistry | None = None
    _lock_class = threading.Lock()

    def __init__(self) -> None:
        """Initialize the registry (private - use get_instance())."""
        from .config import LogConfig

        self._holders: list[LogConfigHolder] = []
        self._lock = threading.RLock()
        self._default_config: LogConfig = LogConfig.from_params("info")

    @classmethod
    def get_instance(cls) -> LogConfigRegistry:
        """
        Get the singleton instance of LogConfigRegistry.

        Returns:
            The singleton LogConfigRegistry instance

        Thread-safe lazy initialization.
        """
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance (for testing only).

        Warning:
            This should only be used in test cleanup to reset state.
        """
        with cls._lock_class:
            cls._instance = None

    def create_holder(self, config: LogConfig | None = None) -> LogConfigHolder:
        """
        Create and register a new LogConfigHolder.

        Args:
            config: LogConfig to wrap. If None, uses default config.

        Returns:
            New LogConfigHolder registered with this registry
        """
        from .config_holder import LogConfigHolder

        with self._lock:
            holder = LogConfigHolder(config or self._default_config)
            self._holders.append(holder)
            return holder

    def set_default_config(self, config: LogConfig) -> None:
        """
        Set the default config for new holders.

        Args:
            config: LogConfig to use as default for new holders
        """
        with self._lock:
            self._default_config = config

    def get_default_config(self) -> LogConfig:
        """Get the current default config."""
        with self._lock:
            return self._default_config

    def update_all(self, new_config: LogConfig) -> None:
        """
        Update all registered holders atomically.

        Args:
            new_config: New LogConfig to apply to all holders
        """
        with self._lock:
            self._default_config = new_config
            holders_copy = list(self._holders)

        # Update outside lock to avoid deadlock with holder locks
        for holder in holders_copy:
            holder.update(new_config)

    def update_display_options(
        self,
        colors: bool | None = None,
        location: int | None = None,
        location_color: str | None = None,
        micros: bool | None = None,
    ) -> None:
        """
        Update only display options on all holders (partial update).

        Preserves level and other settings, only updating specified display options.

        Args:
            colors: New colors setting (None to keep current)
            location: New location depth (None to keep current)
            location_color: New location color (None to keep current)
            micros: New microseconds setting (None to keep current)
        """
        from .config import LogConfig

        with self._lock:
            holders_copy = list(self._holders)

        for holder in holders_copy:
            current = holder.config
            new_config = LogConfig(
                level=current.level,
                location=location if location is not None else current.location,
                micros=micros if micros is not None else current.micros,
                colors=colors if colors is not None else current.colors,
                location_color=(
                    location_color
                    if location_color is not None
                    else current.location_color
                ),
            )
            holder.update(new_config)

    def holder_count(self) -> int:
        """Get number of registered holders (for testing/debugging)."""
        with self._lock:
            return len(self._holders)

    def clear_holders(self) -> None:
        """
        Clear all registered holders (for testing only).

        Warning:
            This will break existing formatters that reference these holders.
        """
        with self._lock:
            self._holders.clear()
