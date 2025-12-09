"""
Configuration management module for loading and resolving YAML configuration files.

This module provides a Config class that extends DotDict to handle YAML configuration
files with variable substitution capabilities, environment variable overrides, and
file inclusion support via !include tags.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from appinfra.dot_dict import DotDict

from .constants import MAX_CONFIG_SIZE_BYTES

# Helper functions for Config._load()


def _preserve_config_attributes(config_instance: Any) -> dict[str, Any]:
    """Preserve configuration attributes before clearing."""
    return {
        "enable_env_overrides": getattr(config_instance, "_enable_env_overrides", True),
        "env_prefix": getattr(config_instance, "_env_prefix", "INFRA_"),
        "merge_strategy": getattr(config_instance, "_merge_strategy", "replace"),
        "resolve_paths": getattr(config_instance, "_resolve_paths", True),
    }


def _restore_config_attributes(
    config_instance: Any, preserved_attrs: dict[str, Any]
) -> None:
    """Restore configuration attributes after clearing."""
    config_instance._enable_env_overrides = preserved_attrs["enable_env_overrides"]
    config_instance._env_prefix = preserved_attrs["env_prefix"]
    config_instance._merge_strategy = preserved_attrs["merge_strategy"]
    config_instance._resolve_paths = preserved_attrs["resolve_paths"]


def _check_file_size(fname_path: Any) -> None:
    """Check file size limit to prevent DoS attacks."""
    file_size = os.path.getsize(fname_path)
    if file_size > MAX_CONFIG_SIZE_BYTES:
        raise ValueError(
            f"Configuration file '{fname_path}' is {file_size} bytes, "
            f"exceeding maximum size of {MAX_CONFIG_SIZE_BYTES} bytes "
            f"({MAX_CONFIG_SIZE_BYTES // (1024 * 1024)} MB)"
        )


def _get_project_root_from_config(config_path: Path) -> Path | None:
    """
    Determine project root from config file location.

    Searches upward from the config file's directory for a directory
    containing an 'etc' folder. This allows appinfra to work correctly
    when used as a submodule, where the consuming project's config
    defines the security boundary.

    Args:
        config_path: Resolved path to the config file being loaded

    Returns:
        Path to project root, or None if not determinable
    """
    # Search upward from the config file's directory
    for parent in config_path.parents:
        if (parent / "etc").is_dir():
            return parent

    # Fallback: use config file's parent directory
    return config_path.parent


def _load_yaml_with_includes(
    fname_path: Any, merge_strategy: str, project_root: Path | None = None
) -> tuple[Any, dict[str, Path | None]]:
    """
    Load YAML file with include support.

    Args:
        fname_path: Path to the YAML file to load
        merge_strategy: Strategy for merging includes
        project_root: Optional project root to restrict includes (security feature)
    """
    from appinfra.yaml import load as yaml_load

    with open(fname_path) as f:
        try:
            return yaml_load(
                f,
                current_file=fname_path,
                merge_strategy=merge_strategy,
                track_sources=True,
                project_root=project_root,
            )
        except yaml.YAMLError as e:
            raise e


class Config(DotDict):
    """
    Configuration class that loads YAML files and resolves variable substitutions.

    Extends DotDict to provide a dictionary-like interface for configuration data.
    Supports variable substitution using ${variable_name} syntax in YAML values.
    Supports environment variable overrides using INFRA_* prefix.
    Supports file inclusion via !include tags with circular dependency detection.

    Environment Variable Override Format:
        INFRA_<SECTION>_<SUBSECTION>_<KEY>=value

    Examples:
        INFRA_LOGGING_LEVEL=debug
        INFRA_PGSERVER_PORT=5432
        INFRA_TEST_LOGGING_LEVEL=info

    Include Example:
        # In config.yaml:
        database: !include "./database_config.yaml"

        # Supports relative paths (resolved from config file's directory)
        # Supports absolute paths
        # Detects circular includes

    Example:
        config = Config('config.yaml')
        # Access configuration values like dictionary keys
        value = config.get('database.host')
    """

    def __init__(
        self,
        fname: str,
        enable_env_overrides: bool = True,
        env_prefix: str = "INFRA_",
        merge_strategy: str = "replace",
        resolve_paths: bool = True,
    ):
        """
        Initialize configuration from a YAML file with optional environment variable overrides.

        Args:
            fname: Path to the YAML configuration file
            enable_env_overrides: Whether to apply environment variable overrides
            env_prefix: Prefix for environment variables (default: 'INFRA_')
            merge_strategy: Strategy for handling includes - "replace" or "merge" (default: "replace")
                           Note: Currently only "replace" is fully supported
            resolve_paths: Whether to resolve relative paths to absolute paths (default: True)
                          Only paths starting with './' or '../' are resolved
        """
        super().__init__()  # Initialize DotDict first
        self._enable_env_overrides = enable_env_overrides
        self._env_prefix = env_prefix
        self._merge_strategy = merge_strategy
        self._resolve_paths = resolve_paths
        self._load(fname)

    def _load(self, fname: str) -> None:
        """
        Load configuration from YAML file and resolve variable substitutions.

        Supports !include tags for including other YAML files.

        Args:
            fname: Path to the YAML configuration file

        Raises:
            yaml.YAMLError: If the YAML file is malformed or includes are circular
        """
        preserved_attrs = _preserve_config_attributes(self)
        self.clear()
        _restore_config_attributes(self, preserved_attrs)

        fname_path = Path(fname).resolve()
        _check_file_size(fname_path)

        # Determine project root from config file location for security checks.
        # This allows appinfra to work correctly when used as a submodule,
        # where the consuming project's config should define the boundary.
        proj_root = _get_project_root_from_config(fname_path)

        config_data, source_map = _load_yaml_with_includes(
            fname_path, self._merge_strategy, project_root=proj_root
        )
        if not self._resolve_paths:
            source_map = {}

        if self._resolve_paths and source_map:
            config_data = self._resolve_paths_in_data(config_data, source_map)

        if self._enable_env_overrides:
            config_data = self._apply_env_overrides(config_data)

        self.set(**config_data)
        self.set(**self._resolve(self.dict()))

    def _resolve(self, content: Any) -> Any:
        """
        Recursively resolve variable substitutions in configuration content.

        Variables are specified using ${variable_name} syntax and are replaced
        with values from the configuration itself, enabling hierarchical references.

        Args:
            content: Configuration content (dict, list, str, or other)

        Returns:
            Resolved content with variable substitutions applied
        """
        if isinstance(content, dict):
            # Recursively resolve all dictionary values
            keys = [k for k in content.keys()]
            for k in keys:
                content[k] = self._resolve(content[k])
        elif isinstance(content, str):
            # Replace ${variable_name} patterns with actual values
            # Restrict to valid config keys (alphanumeric + dot + underscore) to prevent ReDoS
            return re.sub(r"\$\{([a-zA-Z0-9_.]+)\}", self._substitute_var, content)
        return content

    def _substitute_var(self, match: re.Match) -> str:
        """
        Substitute a variable reference with its value.

        Args:
            match: Regex match object containing the variable name

        Returns:
            String value of the variable

        Raises:
            DotDictPathNotFoundError: If the variable is not defined
        """
        from appinfra.dot_dict import DotDictPathNotFoundError

        var_name = match.group(1)
        if not self.has(var_name):
            raise DotDictPathNotFoundError(self, var_name)
        return str(self.get(var_name))

    def _should_resolve_path(self, value: Any) -> bool:
        """
        Determine if a value should be resolved as a relative path.

        Only resolves values that:
        - Are strings
        - Start with './' or '../' (explicit relative paths)
        - Don't contain '://' (URLs)
        - Are not already absolute paths

        Args:
            value: Value to check

        Returns:
            True if the value should be resolved as a path
        """
        if not isinstance(value, str) or not value:
            return False

        # Skip URLs (e.g., http://example.com/path or file://path)
        if "://" in value:
            return False

        # Skip absolute paths (already resolved)
        if Path(value).is_absolute():
            return False

        # Only resolve explicit relative paths
        if value.startswith("./") or value.startswith("../"):
            return True

        return False

    def _resolve_path_value(self, value: str, source_file: Path) -> str:
        """
        Resolve a relative path to absolute based on source file location.

        Args:
            value: Relative path string
            source_file: Path to the config file where this value was defined

        Returns:
            Absolute path as string
        """
        if not self._should_resolve_path(value):
            return value

        try:
            # Resolve relative to source file's directory
            value_path = Path(value)
            resolved = (source_file.parent / value_path).resolve()
            return str(resolved)
        except Exception:
            # If resolution fails, return original value
            return value

    def _resolve_string_value(
        self, value: str, config_path: str, source_map: dict[str, Path | None]
    ) -> str:
        """
        Resolve a string value if it's a relative path.

        Args:
            value: String value to resolve
            config_path: Path in config hierarchy where this value is located
            source_map: Map of config paths to source file paths

        Returns:
            Resolved string value (or original if not a path)
        """
        source_file = source_map.get(config_path)
        if source_file and self._should_resolve_path(value):
            return self._resolve_path_value(value, source_file)
        return value

    def _resolve_dict_paths(
        self, data: dict, source_map: dict[str, Path | None], parent_path: str
    ) -> dict:
        """
        Resolve relative paths in a dictionary.

        Args:
            data: Dictionary to process
            source_map: Map of config paths to source file paths
            parent_path: Current path in the config hierarchy

        Returns:
            Dictionary with resolved paths
        """
        resolved_dict = {}
        for key, value in data.items():
            full_path = f"{parent_path}.{key}" if parent_path else key

            if isinstance(value, (dict, list)):
                resolved_dict[key] = self._resolve_paths_in_data(
                    value, source_map, full_path
                )
            elif isinstance(value, str):
                resolved_dict[key] = self._resolve_string_value(
                    value, full_path, source_map
                )
            else:
                resolved_dict[key] = value

        return resolved_dict

    def _resolve_list_paths(
        self, data: list, source_map: dict[str, Path | None], parent_path: str
    ) -> list:
        """
        Resolve relative paths in a list.

        Args:
            data: List to process
            source_map: Map of config paths to source file paths
            parent_path: Current path in the config hierarchy

        Returns:
            List with resolved paths
        """
        resolved_list = []
        for idx, item in enumerate(data):
            item_path = f"{parent_path}[{idx}]"

            if isinstance(item, (dict, list)):
                resolved_list.append(
                    self._resolve_paths_in_data(item, source_map, item_path)
                )
            elif isinstance(item, str):
                resolved_list.append(
                    self._resolve_string_value(item, item_path, source_map)
                )
            else:
                resolved_list.append(item)

        return resolved_list

    def _resolve_paths_in_data(
        self, data: Any, source_map: dict[str, Path | None], parent_path: str = ""
    ) -> Any:
        """
        Recursively resolve relative paths in configuration data.

        Args:
            data: Configuration data (dict, list, or scalar)
            source_map: Map of config paths to source file paths
            parent_path: Current path in the config hierarchy (for dict keys)

        Returns:
            Configuration data with relative paths resolved to absolute
        """
        if isinstance(data, dict):
            return self._resolve_dict_paths(data, source_map, parent_path)

        elif isinstance(data, list):
            return self._resolve_list_paths(data, source_map, parent_path)

        else:
            # Scalar value - check if it's a path to resolve
            if isinstance(data, str) and parent_path:
                return self._resolve_string_value(data, parent_path, source_map)
            return data

    def _apply_env_overrides(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply environment variable overrides to configuration data.

        Args:
            config_data: Configuration data dictionary

        Returns:
            Configuration data with environment variable overrides applied
        """
        env_overrides = self._collect_env_vars()

        for env_key, env_value in env_overrides.items():
            # Convert INFRA_LOGGING_LEVEL -> ['logging', 'level']
            config_path = self._env_key_to_path(env_key)

            # Apply the override
            self._set_nested_value(config_data, config_path, env_value)

        return config_data

    def _collect_env_vars(self) -> dict[str, str]:
        """
        Collect all environment variables with the configured prefix.

        Returns:
            Dictionary of environment variable names and values
        """
        env_vars = {}
        for key, value in os.environ.items():
            if key.startswith(self._env_prefix):
                env_vars[key] = value
        return env_vars

    def _env_key_to_path(self, env_key: str) -> list[str]:
        """
        Convert environment variable key to configuration path.

        Args:
            env_key: Environment variable key (e.g., 'INFRA_LOGGING_LEVEL')

        Returns:
            List of path components (e.g., ['logging', 'level'])
        """
        # Remove prefix and split by underscore
        path_parts = env_key[len(self._env_prefix) :].lower().split("_")
        return path_parts

    def _set_nested_value(self, data: dict, path: list[str], value: Any) -> None:
        """
        Set a nested value in the configuration dictionary.

        Args:
            data: Configuration dictionary to modify
            path: List of keys representing the path to the value
            value: Value to set
        """
        current = data
        for part in path[:-1]:
            if part not in current or not isinstance(current.get(part), dict):
                current[part] = {}
            current = current[part]

        # Convert value to appropriate type
        converted_value = self._convert_env_value(value)
        current[path[-1]] = converted_value

    def _convert_env_value(
        self, value: str
    ) -> bool | int | float | str | list[str] | None:
        """
        Convert environment variable string to appropriate type.

        Args:
            value: Environment variable value as string

        Returns:
            Converted value with appropriate type
        """
        # Handle null/none values
        if value.lower() in ("null", "none", ""):
            return None

        # Handle boolean values
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # Handle list values (comma-separated)
        if "," in value:
            return [self._convert_env_value(v.strip()) for v in value.split(",")]  # type: ignore[misc]

        # Handle numeric values
        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # Return as string
        return value

    def get_env_overrides(self) -> dict[str, Any]:
        """
        Get all environment variable overrides that would be applied.

        Returns:
            Dictionary of environment variable overrides
        """
        if not self._enable_env_overrides:
            return {}

        env_vars = self._collect_env_vars()
        overrides = {}

        for env_key, env_value in env_vars.items():
            config_path = self._env_key_to_path(env_key)
            path_str = ".".join(config_path)
            overrides[path_str] = self._convert_env_value(env_value)

        return overrides

    def validate(self, raise_on_error: bool = True) -> bool | Any:
        """
        Validate configuration against schema (if pydantic is installed).

        This method provides optional schema validation using Pydantic models.
        If pydantic is not installed, this method returns True (no validation).

        Args:
            raise_on_error: If True, raise ValidationError on invalid config.
                           If False, return False on invalid config.

        Returns:
            If pydantic installed: validated config object or raises/returns False
            If pydantic not installed: True (no validation performed)

        Raises:
            ValidationError: If config is invalid and raise_on_error=True

        Example:
            # Install validation support: pip install infra[validation]
            import logging

            lg = logging.getLogger(__name__)
            config = Config('etc/infra.yaml')
            try:
                validated = config.validate()
                lg.info("Configuration is valid!")
            except ValidationError as e:
                lg.error(f"Invalid configuration: {e}")
        """
        try:
            from ..config import PYDANTIC_AVAILABLE, validate_config

            if not PYDANTIC_AVAILABLE:
                # Pydantic not installed - skip validation
                return True

            # Convert config to dict for validation
            config_dict = dict(self)

            # Validate using pydantic schema
            if raise_on_error:
                return validate_config(config_dict)
            else:
                try:
                    return validate_config(config_dict)
                except Exception:
                    return False

        except ImportError:
            # Config schemas module not available
            return True


# Project path utilities
def get_project_root() -> Path:
    """
    Get the project root directory by looking for the etc/infra.yaml file.

    This function searches upward from the current file's location until it finds
    a directory containing etc/infra.yaml, which indicates the project root.

    Returns:
        Path to the project root directory

    Raises:
        FileNotFoundError: If the project root cannot be found
    """
    current_path = Path(__file__).resolve()

    # Search upward from the current file's location
    for parent in current_path.parents:
        if (parent / "etc" / "infra.yaml").exists():
            return parent

    raise FileNotFoundError(
        "Could not find project root with etc/infra.yaml. "
        "Make sure you're running from within the infra project directory."
    )


def get_etc_dir() -> Path:
    """
    Get the etc directory path relative to the project root.

    Returns:
        Path to the etc directory (project_root/etc)

    Raises:
        FileNotFoundError: If the project root cannot be found
    """
    return get_project_root() / "etc"


def get_config_path(config_file: str = "infra.yaml") -> Path:
    """
    Get the path to a configuration file in the etc directory.

    Args:
        config_file: Name of the configuration file (default: "infra.yaml")

    Returns:
        Path to the configuration file

    Raises:
        FileNotFoundError: If the project root cannot be found
    """
    return get_etc_dir() / config_file


# Constants for common paths
PROJECT_ROOT: Path | None
ETC_DIR: Path | None
DEFAULT_CONFIG_FILE: Path | None

try:
    PROJECT_ROOT = get_project_root()
    ETC_DIR = get_etc_dir()
    DEFAULT_CONFIG_FILE = get_config_path("infra.yaml")
except FileNotFoundError:
    # Set to None if project root cannot be found (e.g., during package installation)
    PROJECT_ROOT = None
    ETC_DIR = None
    DEFAULT_CONFIG_FILE = None


# Lazy-loaded default config (convenience function for examples/scripts).
#
# NOTE: This global is intentional and acceptable because:
# 1. It's lazy-loaded (no import-time side effects)
# 2. Only used in examples/ - core library code uses explicit Config(path)
# 3. Returns None gracefully if no config file exists
# 4. Tests create fresh Config() instances, so no test isolation issues
#
# Production code should use: Config(path) or AppBuilder().with_config(...)
_default_config: Config | None = None


def get_default_config() -> Config | None:
    """
    Get the default configuration, lazily loading it on first access.

    This is a convenience function for examples and quick scripts. Production code
    should use explicit Config(path) instantiation for better control and testability.

    This function avoids executing file I/O at module import time, which improves
    test isolation and prevents issues in environments without config files.

    Returns:
        Config instance loaded from DEFAULT_CONFIG_FILE, or None if file not found

    Example:
        config = get_default_config()
        if config:
            db_host = config.database.host
    """
    global _default_config

    # Return cached config if already loaded
    if _default_config is not None:
        return _default_config

    # Load config if file exists
    if DEFAULT_CONFIG_FILE is not None:
        try:
            _default_config = Config(str(DEFAULT_CONFIG_FILE))
        except FileNotFoundError:
            _default_config = None

    return _default_config
