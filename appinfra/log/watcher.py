"""
File-based configuration watcher for hot-reload.

This module provides a file watcher that monitors configuration files for changes
and automatically reloads logging configuration when modifications are detected.
Uses the watchdog library for efficient file system monitoring.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import LogConfig


class LogConfigWatcher:
    """
    Watches configuration file for changes and applies updates.

    Uses watchdog for efficient file system monitoring with
    debouncing to avoid rapid re-reads on multiple write events.

    Example:
        >>> watcher = LogConfigWatcher.get_instance()
        >>> watcher.configure("etc/app.yaml", section="logging")
        >>> watcher.start()
        >>> # File changes are now automatically detected
        >>> watcher.stop()

    Note:
        Requires watchdog package. Install with: pip install appinfra[hotreload]
    """

    _instance: LogConfigWatcher | None = None
    _lock_class = threading.Lock()

    def __init__(self) -> None:
        """Initialize the watcher (private - use get_instance())."""
        self._observer: Any = None  # watchdog Observer
        self._config_path: Path | None = None
        self._section: str = "logging"
        self._debounce_ms: int = 500
        self._last_reload: float = 0
        self._lock = threading.RLock()
        self._running = False
        self._on_reload_callbacks: list[Callable[[LogConfig], None]] = []
        self._watched_files: set[Path] = set()  # All files to watch (main + includes)
        self._watched_dirs: set[Path] = set()  # Directories being watched

    @classmethod
    def get_instance(cls) -> LogConfigWatcher:
        """
        Get the singleton instance of LogConfigWatcher.

        Returns:
            The singleton LogConfigWatcher instance

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
            Stops the watcher if running.
        """
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    def configure(
        self,
        config_path: str | Path,
        section: str = "logging",
        debounce_ms: int = 500,
    ) -> LogConfigWatcher:
        """
        Configure the watcher (fluent API).

        Args:
            config_path: Path to the configuration file to watch
            section: Config section containing logging config (default: "logging")
            debounce_ms: Milliseconds to wait before applying changes (default: 500)

        Returns:
            Self for method chaining

        Example:
            >>> watcher.configure("etc/app.yaml", section="logging", debounce_ms=1000).start()
        """
        with self._lock:
            self._config_path = Path(config_path).resolve()
            self._section = section
            self._debounce_ms = debounce_ms
        return self

    def _create_file_handler(self) -> Any:  # pragma: no cover
        """Create watchdog event handler for config file changes."""
        from watchdog.events import FileSystemEventHandler

        watcher = self  # Closure reference

        class ConfigFileHandler(FileSystemEventHandler):  # type: ignore[misc]
            def on_modified(self, event: Any) -> None:
                if event.is_directory:
                    return
                modified_path = Path(event.src_path).resolve()
                # Trigger reload if ANY watched file changes (main or includes)
                if modified_path in watcher._watched_files:
                    watcher._on_file_changed()

        return ConfigFileHandler()

    def _get_source_files_from_config(self) -> set[Path]:
        """Load config and return all source files (main + includes)."""
        if self._config_path is None:
            return set()
        try:
            from appinfra.app.cfg import Config

            config = Config(str(self._config_path))
            return config.get_source_files()
        except Exception:
            # Fall back to just the main config file
            return {self._config_path}

    def _update_watched_directories(self) -> None:
        """Update observer to watch all directories containing source files."""
        if self._observer is None:
            return

        # Get unique directories from watched files
        new_dirs = {f.parent for f in self._watched_files}

        # Add watchers for new directories
        for dir_path in new_dirs - self._watched_dirs:
            self._observer.schedule(
                self._create_file_handler(), str(dir_path), recursive=False
            )

        self._watched_dirs = new_dirs

    def start(self) -> None:
        """Start watching for file changes."""
        try:
            from watchdog.observers import Observer
        except ImportError:
            raise ImportError(
                "watchdog is required for hot-reload. "
                "Install with: pip install appinfra[hotreload]"
            ) from None

        with self._lock:  # pragma: no cover
            if self._running:
                return
            if self._config_path is None:
                raise ValueError("Config path not set. Call configure() first.")

            # Get all source files (main config + includes)
            self._watched_files = self._get_source_files_from_config()

            self._observer = Observer()
            # Watch all directories containing source files
            self._watched_dirs = {f.parent for f in self._watched_files}
            for dir_path in self._watched_dirs:
                self._observer.schedule(
                    self._create_file_handler(), str(dir_path), recursive=False
                )
            self._observer.start()
            self._running = True

    def stop(self) -> None:
        """Stop watching for file changes."""
        with self._lock:
            if self._observer is not None:  # pragma: no cover
                self._observer.stop()
                self._observer.join(timeout=2.0)
                self._observer = None
            self._running = False
            self._watched_files = set()
            self._watched_dirs = set()

    def is_running(self) -> bool:
        """Check if watcher is active."""
        with self._lock:
            return self._running

    def _on_file_changed(self) -> None:
        """Handle file change event with debouncing."""
        now = time.time() * 1000  # milliseconds

        with self._lock:
            if now - self._last_reload < self._debounce_ms:
                return  # Debounce
            self._last_reload = now

        # Reload outside lock to avoid blocking
        self._reload_config()

    def _apply_config_update(self, config_dict: dict[str, Any]) -> Any:
        """Parse config and update registry. Returns new LogConfig."""
        from .config import LogConfig
        from .config_registry import LogConfigRegistry

        new_log_config = LogConfig.from_config(config_dict, self._section)
        registry = LogConfigRegistry.get_instance()
        registry.update_all(new_log_config)
        self._update_level_manager(config_dict)
        return new_log_config

    def _notify_callbacks(self, new_log_config: Any) -> None:
        """Notify all registered callbacks of config change."""
        with self._lock:
            callbacks = list(self._on_reload_callbacks)

        for callback in callbacks:
            try:
                callback(new_log_config)
            except Exception:
                pass  # Don't let callback errors break reload

    def _reload_config(self) -> None:
        """Reload configuration from file."""
        if self._config_path is None:
            return

        try:
            from appinfra.app.cfg import Config

            config = Config(str(self._config_path))
            new_log_config = self._apply_config_update(config.dict())

            # Update watched files in case includes changed
            new_source_files = config.get_source_files()
            with self._lock:
                self._watched_files = new_source_files
                self._update_watched_directories()

            self._notify_callbacks(new_log_config)
        except Exception as e:
            print(f"[LogConfigWatcher] Failed to reload config: {e}", file=sys.stderr)

    def _update_level_manager(self, config_dict: dict[str, Any]) -> None:
        """Update level manager with new topic rules."""
        from .level_manager import LogLevelManager

        # Navigate to logging section
        section_parts = self._section.split(".")
        current: Any = config_dict
        for part in section_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return

        if not isinstance(current, dict):
            return

        topics = current.get("topics")
        if topics and isinstance(topics, dict):
            manager = LogLevelManager.get_instance()
            # Clear old yaml rules and add new ones
            manager.clear_rules(source="yaml")
            manager.add_rules_from_dict(topics, source="yaml", priority=1)

    def add_reload_callback(self, callback: Callable[[LogConfig], None]) -> None:
        """
        Add callback to be notified on config reload.

        Args:
            callback: Function to call when config is reloaded.
                     Receives the new LogConfig as argument.
        """
        with self._lock:
            self._on_reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: Callable[[LogConfig], None]) -> None:
        """
        Remove a previously registered callback.

        Args:
            callback: Callback function to remove
        """
        with self._lock:
            try:
                self._on_reload_callbacks.remove(callback)
            except ValueError:
                pass  # Callback not found, ignore

    def reload_now(self) -> None:
        """
        Force immediate config reload.

        Useful for testing or manual trigger without file modification.
        """
        self._reload_config()
