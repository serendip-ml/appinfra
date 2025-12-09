"""
Unified exception hierarchy for the infra framework.

This module provides a consistent exception hierarchy for all framework errors,
making it easier to catch and handle framework-specific exceptions.
"""

from typing import Any


class InfraError(Exception):
    """
    Base exception for all infra framework errors.

    All framework-specific exceptions inherit from this base class,
    allowing users to catch all framework errors with a single except clause.

    Example:
        try:
            app.run()
        except InfraError as e:
            logger.error(f"Framework error: {e}")
    """

    def __init__(self, message: str, **context: Any) -> None:
        """
        Initialize the exception with a message and optional context.

        Args:
            message: Human-readable error message
            **context: Additional context information (stored in self.context)
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        """String representation with context if available."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class ConfigError(InfraError):
    """
    Configuration-related errors.

    Raised when there are issues with configuration loading, parsing,
    validation, or access.

    Examples:
        - Config file not found
        - Invalid YAML syntax
        - Missing required configuration value
        - Invalid configuration value type
    """

    pass


class DatabaseError(InfraError):
    """
    Database-related errors.

    Raised when there are issues with database connections, queries,
    or database operations.

    Examples:
        - Connection failed
        - Query execution error
        - Transaction error
        - Health check failed
    """

    pass


class LoggingError(InfraError):
    """
    Logging-related errors.

    Raised when there are issues with logging configuration or operation.

    Examples:
        - Invalid log level
        - Handler configuration error
        - Formatter error
        - Callback registration error
    """

    pass


class ValidationError(InfraError):
    """
    Validation-related errors.

    Raised when data validation fails, including configuration validation
    and input validation.

    Examples:
        - Schema validation failed
        - Type validation failed
        - Required field missing
        - Value out of range
    """

    pass


class ToolError(InfraError):
    """
    Tool-related errors.

    Raised when there are issues with tool registration, configuration,
    or execution.

    Examples:
        - Tool not found
        - Duplicate tool registration
        - Tool execution failed
        - Missing required tool attribute
    """

    pass


class ServerError(InfraError):
    """
    Server-related errors.

    Raised when there are issues with server startup, shutdown, or
    request handling.

    Examples:
        - Server startup failed
        - Port already in use
        - Request handler error
        - Middleware error
    """

    pass


class ObservabilityError(InfraError):
    """
    Observability-related errors.

    Raised when there are issues with observability hooks, callbacks,
    or monitoring.

    Examples:
        - Hook registration failed
        - Callback execution error
        - Invalid hook event type
    """

    pass


# Maintain backward compatibility with existing exception classes
# by keeping them importable from their original locations while
# also making them inherit from the new hierarchy

# These are defined in their respective modules:
# - appinfra.app.errors: ApplicationError, ToolRegistrationError, etc.
# - appinfra.log.exceptions: LogError, InvalidLogLevelError, etc.
# - appinfra.net.exceptions: ServerError (original), etc.
#
# The new hierarchy provides a unified way to catch all framework errors,
# while the specific exceptions in each module provide detailed error handling.
