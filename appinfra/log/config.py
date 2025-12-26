"""
Configuration classes for the logging system.

This module provides immutable configuration classes for loggers and formatters,
ensuring consistent configuration across the logging system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChildLogConfig:
    """
    Immutable configuration for child loggers.

    Child loggers only control their log level. Global settings like location,
    colors, and micros are read from the registry's root config.
    """

    level: int | bool = logging.INFO  # int for normal levels, False to disable logging


@dataclass(frozen=True)
class LogConfig:
    """
    Immutable configuration for root loggers.

    This class holds all configuration parameters for a logger instance,
    ensuring consistency and preventing accidental modifications.

    Note: Child loggers use ChildLogConfig which only contains level.
    Global display settings (location, colors, micros) are read from the
    registry's root config for hot-reload support.
    """

    level: int | bool = logging.INFO  # int for normal levels, False to disable logging
    location: int = 0
    micros: bool = False
    colors: bool = True
    location_color: str | None = None  # ANSI color code for code locations

    @staticmethod
    def _resolve_level(level: str | int | bool) -> int | bool:
        """Resolve level parameter to int or False."""
        from .constants import LogConstants
        from .exceptions import InvalidLogLevelError

        if isinstance(level, bool):
            return False if not level else logging.INFO
        elif isinstance(level, str):
            if level.isnumeric():
                return int(level)
            elif level in LogConstants.LEVEL_NAMES:
                return LogConstants.LEVEL_NAMES[level]
            else:
                raise InvalidLogLevelError(level)
        return level

    @classmethod
    def from_params(
        cls,
        level: str | int | bool,
        location: bool | int = 0,
        micros: bool = False,
        colors: bool = True,
        location_color: str | None = None,
    ) -> LogConfig:
        """
        Create LogConfig from individual parameters.

        Args:
            level: Log level (string name, numeric value, or False to disable logging)
            location: Location display level (bool or int)
            micros: Whether to show microsecond precision
            colors: Whether to enable colored output
            location_color: ANSI color code for code locations (e.g., ColorManager.CYAN)

        Returns:
            LogConfig instance
        """
        resolved_level = cls._resolve_level(level)
        resolved_location = (
            1 if location is True else (0 if location is False else int(location))
        )
        resolved_location_color = cls._resolve_location_color(location_color)

        return cls(
            level=resolved_level,
            location=resolved_location,
            micros=micros,
            colors=colors,
            location_color=resolved_location_color,
        )

    @staticmethod
    def _navigate_to_section(config_dict: dict, section: str) -> dict:
        """Navigate to specified section in config dict."""
        section_parts = section.split(".")
        current = config_dict

        for part in section_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Fall back to empty dict if section not found
                return {}

        return current

    @staticmethod
    def _resolve_location_color(location_color: Any) -> Any:
        """Resolve location color name to ANSI code if needed."""
        if not isinstance(location_color, str):
            return location_color

        from .colors import ColorManager

        resolved_color = ColorManager.from_name(location_color)
        if resolved_color is not None:
            return resolved_color
        # Keep original string (might be direct ANSI code)
        return location_color

    @classmethod
    def from_config(cls, config_dict: dict, section: str = "logging") -> LogConfig:
        """
        Create LogConfig from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary (e.g., from Config class)
            section: Configuration section to use (default: "logging")

        Returns:
            LogConfig instance

        Example:
            from appinfra.config import Config
            config = Config("etc/infra.yaml")
            log_config = LogConfig.from_config(config.dict(), "test.logging")
        """
        # Navigate to the specified section
        current = cls._navigate_to_section(config_dict, section)

        # Extract values with defaults
        level = current.get("level", "info")
        location = current.get("location", 0)
        micros = current.get("microseconds", current.get("micros", False))
        colors = current.get("colors", True)
        if isinstance(colors, dict):
            colors = colors.get("enabled", True)
        location_color = current.get("location_color", None)

        # Handle string "false" to disable logging
        if level == "false":
            level = False

        # Resolve location_color name to ANSI code
        location_color = cls._resolve_location_color(location_color)

        return cls.from_params(
            level=level,
            location=location,
            micros=micros,
            colors=colors,
            location_color=location_color,
        )
