"""
Factory classes for creating and configuring loggers.

This module provides factory classes for creating loggers with consistent
configuration and proper setup of handlers and formatters.
"""

import collections
import logging
from typing import Any

from .callback import CallbackRegistry
from .config import LogConfig
from .formatters import LogFormatter
from .logger import Logger
from .logger_with_sep import LoggerWithSeparator


class LoggerFactory:
    """Factory for creating and configuring loggers."""

    @staticmethod
    def create_root(config: LogConfig, logger_class: type[Logger] = Logger) -> Logger:
        """
        Create a root logger with the specified configuration.

        Args:
            config: Logger configuration
            logger_class: Logger class to use

        Returns:
            Configured root logger

        Example:
            >>> from appinfra.log import LoggerFactory, LogConfig
            >>>
            >>> config = LogConfig.from_params(level="info", colors=True)
            >>> logger = LoggerFactory.create_root(config)
            >>> logger.info("Application started")
            [12:34:56,789] [I] Application started [1234] [/]
        """
        return LoggerFactory.create("/", config, logger_class)

    @staticmethod
    def _get_effective_config(name: str, config: LogConfig) -> LogConfig:
        """Get effective config with topic-based level override if applicable."""
        from .level_manager import LogLevelManager

        level_manager = LogLevelManager.get_instance()
        effective_level = level_manager.get_effective_level(name)

        if effective_level is None:
            return config

        if isinstance(effective_level, str):
            resolved_level = getattr(logging, effective_level.upper(), logging.INFO)
        else:
            resolved_level = effective_level

        return LogConfig(
            level=resolved_level,
            location=config.location,
            micros=config.micros,
            colors=config.colors,
            location_color=getattr(config, "location_color", None),
        )

    @staticmethod
    def _setup_console_handler(config: LogConfig) -> logging.Handler:
        """Set up and return console handler with formatter."""
        handler = logging.StreamHandler()
        handler.setLevel(config.level)

        formatter = LogFormatter(config)
        handler.setFormatter(formatter)

        return handler

    @staticmethod
    def create(
        name: str,
        config: LogConfig,
        logger_class: type[Logger] = Logger,
        extra: dict[str, Any] | collections.OrderedDict | None = None,
    ) -> Logger:
        """
        Create a logger with the specified configuration.

        Args:
            name: Logger name
            config: Logger configuration
            logger_class: Logger class to use
            extra: Pre-populated extra fields to include in all log records

        Returns:
            Configured logger instance

        Example:
            >>> from appinfra.log import LoggerFactory, LogConfig
            >>>
            >>> config = LogConfig.from_params(level="debug")
            >>> db_logger = LoggerFactory.create("/database", config)
            >>> db_logger.info("Connected", extra={"host": "localhost"})
            [12:34:56,789] [I] Connected [host:localhost] [1234] [/database]
            >>>
            >>> # With pre-populated extra fields
            >>> api_logger = LoggerFactory.create(
            ...     "/api", config, extra={"service": "users"}
            ... )
            >>> api_logger.info("Request received")
            [12:34:56,789] [I] Request received [service:users] [1234] [/api]
        """
        logging.setLoggerClass(logger_class)

        # Check if logger already exists
        existing = LoggerFactory._check_existing_logger(name)
        if existing:
            return existing

        # Create new logger
        return LoggerFactory._create_new_logger(name, config, logger_class, extra)

    @staticmethod
    def _check_existing_logger(name: str) -> Logger | None:
        """Check if logger exists and return it."""
        if name in logging.root.manager.loggerDict:
            from typing import cast

            lg = cast(Logger, logging.getLogger(name))
            if hasattr(lg, "trace2"):
                lg.trace2("logger already exists", extra={"logger": name})
            return lg
        return None

    @staticmethod
    def _create_new_logger(
        name: str,
        config: LogConfig,
        logger_class: type[Logger],
        extra: dict[str, Any] | collections.OrderedDict | None,
    ) -> Logger:
        """Create a new logger with effective config and handler."""
        callback_registry = CallbackRegistry()
        lg = logger_class(name, config, callback_registry, extra)
        effective_config = LoggerFactory._get_effective_config(name, config)
        lg.setLevel(effective_config.level)

        handler = LoggerFactory._setup_console_handler(effective_config)
        lg.addHandler(handler)
        lg.propagate = False

        lg.trace2(
            "created logger",
            extra={
                "level": logging.getLevelName(effective_config.level),
                "location": effective_config.location,
                "micros": effective_config.micros,
            },
        )
        return lg

    @staticmethod
    def create_child(parent: Logger, name: str) -> Logger:
        """
        Create a child logger from a parent with a single name component.

        This method creates a direct child logger by appending a single name
        to the parent's path. For creating loggers with multiple hierarchical
        components, use derive() instead.

        Examples:
            >>> parent = LoggerFactory.create_root(config)  # name: "/"
            >>> child = LoggerFactory.create_child(parent, "database")
            >>> child.name
            '/database'

            >>> parent = LoggerFactory.create("/infra", config)  # name: "/infra"
            >>> child = LoggerFactory.create_child(parent, "db")
            >>> child.name
            '/infra/db'

        Differences from derive():
            - create_child() takes a single name string
            - derive() takes a string or list of tags and joins them with "/"
            - Use create_child() for simple parent-child relationships
            - Use derive() when you need multiple hierarchical components

        Args:
            parent: Parent logger instance
            name: Single child logger name (no "/" separators)

        Returns:
            Child logger instance with inherited configuration

        See Also:
            derive: Create logger with one or more hierarchical tag components
        """
        full_name = f"{parent.name}/{name}" if parent.name != "/" else f"/{name}"

        # Create child config based on parent
        child_config = LogConfig(
            level=parent.get_level(),
            location=parent.location,
            micros=parent.micros,
            colors=parent.config.colors,
        )

        child_logger = LoggerFactory.create(full_name, child_config, parent.__class__)

        # Inherit callbacks from parent
        parent._callbacks.inherit_to(child_logger._callbacks)

        return child_logger

    @staticmethod
    def derive(parent: Logger, tags: str | list[str]) -> Logger:
        """
        Derive a logger with one or more hierarchical tag components.

        This method creates a derived logger by appending tag(s) to the parent's
        path. When multiple tags are provided (as a list), they are joined with
        "/" to create a multi-level hierarchy. For simple single-name children,
        create_child() provides equivalent functionality with a simpler API.

        Examples:
            >>> parent = LoggerFactory.create_root(config)  # name: "/"
            >>> derived = LoggerFactory.derive(parent, "request")
            >>> derived.name
            '/request'

            >>> # Multiple tags create hierarchical path
            >>> derived = LoggerFactory.derive(parent, ["api", "v1", "users"])
            >>> derived.name
            '/api/v1/users'

            >>> parent = LoggerFactory.create("/infra", config)  # name: "/infra"
            >>> derived = LoggerFactory.derive(parent, ["db", "query"])
            >>> derived.name
            '/infra/db/query'

        Differences from create_child():
            - derive() accepts a string OR list of tags
            - Multiple tags are joined with "/" automatically
            - create_child() only accepts a single name string
            - Both methods are functionally equivalent for single tags

        Use Cases:
            - Use derive() when you have dynamic tag hierarchies
            - Use derive() when tags come from a list/array
            - Use create_child() for static, single-level child creation

        Args:
            parent: Parent logger instance
            tags: Single tag string OR list of tag strings to form hierarchy

        Returns:
            Derived logger instance with inherited configuration

        See Also:
            create_child: Simpler API for creating single-name child loggers
        """
        if isinstance(tags, str):
            tags = [tags]

        prefix = parent.name if parent.name == "/" else parent.name + "/"
        name = prefix + "/".join(tags)

        # Create derived config based on parent
        derived_config = LogConfig(
            level=parent.get_level(),
            location=parent.location,
            micros=parent.micros,
            colors=parent.config.colors,
            location_color=getattr(parent.config, "location_color", None),
        )

        derived_logger = LoggerFactory.create(name, derived_config, parent.__class__)

        # Inherit callbacks from parent
        parent._callbacks.inherit_to(derived_logger._callbacks)

        return derived_logger

    @staticmethod
    def create_with_separator(name: str, config: LogConfig) -> LoggerWithSeparator:
        """
        Create a logger with separator functionality.

        Args:
            name: Logger name
            config: Logger configuration

        Returns:
            Logger with separator functionality
        """
        from typing import cast

        return cast(
            LoggerWithSeparator, LoggerFactory.create(name, config, LoggerWithSeparator)
        )

    @staticmethod
    def create_root_with_separator(config: LogConfig) -> LoggerWithSeparator:
        """
        Create a root logger with separator functionality.

        Args:
            config: Logger configuration

        Returns:
            Root logger with separator functionality
        """
        from typing import cast

        return cast(
            LoggerWithSeparator, LoggerFactory.create_root(config, LoggerWithSeparator)
        )
