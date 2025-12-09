"""
Configuration validation and schema management.

This module provides optional schema validation for configuration files
using Pydantic (if installed).
"""

from typing import Any

try:
    from .schemas import (
        PYDANTIC_AVAILABLE,
        DatabaseConfig,
        InfraConfig,
        LoggingConfig,
        validate_config,
    )
except ImportError:
    # Pydantic not installed - validation not available
    PYDANTIC_AVAILABLE = False
    InfraConfig: type[Any] | None = None  # type: ignore[no-redef]
    LoggingConfig: type[Any] | None = None  # type: ignore[no-redef]
    DatabaseConfig: type[Any] | None = None  # type: ignore[no-redef]

    def validate_config(config_dict: dict[str, Any]) -> dict[str, Any]:  # type: ignore[no-redef,misc]
        """No-op validation when pydantic is not installed."""
        return config_dict


__all__ = [
    "InfraConfig",
    "LoggingConfig",
    "DatabaseConfig",
    "validate_config",
    "PYDANTIC_AVAILABLE",
]
