"""
Custom YAML loader with enhanced key handling and include support.

This module provides a custom YAML loader that automatically converts
certain key types to strings for better compatibility and supports
file inclusion via the !include tag and secrets validation via !secret tag.
"""

import datetime
import re
import warnings
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

# Pattern for environment variable references: ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


class SecretLiteralWarning(UserWarning):
    """Warning emitted when a !secret tagged value appears to be a literal instead of env var."""

    pass


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary to merge into
        override: Dictionary with values to override base

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Loader(yaml.SafeLoader):
    """
    Custom YAML loader with automatic key type conversion and include support.

    Extends the safe YAML loader to:
    1. Automatically convert date and numeric keys to strings
    2. Support file inclusion via !include tag
    3. Detect circular includes
    4. Support configurable merge strategies (replace or merge)

    Example:
        # In your YAML file:
        database:
          connection: !include "./db_config.yaml"

        # Load with custom loader:
        with open('config.yaml') as f:
            config = yaml.load(f, Loader=Loader)
    """

    def __init__(
        self,
        stream: Any,
        current_file: Path | None = None,
        include_chain: set[Path] | None = None,
        merge_strategy: str = "replace",
        track_sources: bool = False,
        project_root: Path | None = None,
        max_include_depth: int = 10,
    ) -> None:
        """
        Initialize the loader with include support.

        Args:
            stream: YAML stream to load
            current_file: Path to the current file being loaded (for relative includes)
            include_chain: Set of files in the current include chain (for circular detection)
            merge_strategy: Strategy for merging includes - "replace" or "merge"
            track_sources: If True, track source file for each value (for path resolution)
            project_root: Optional project root path to restrict includes (prevents path traversal)
            max_include_depth: Maximum allowed depth for nested includes (default: 10)
        """
        super().__init__(stream)
        self.current_file = current_file
        self.include_chain = include_chain if include_chain is not None else set()
        self.merge_strategy = merge_strategy
        self.track_sources = track_sources
        self.project_root = project_root.resolve() if project_root else None
        self.max_include_depth = max_include_depth
        self.source_map: dict[str, Path | None] = {}
        self._path_stack: list = []  # Stack to track current config path during construction
        self._pending_include_maps: dict[
            int, dict[str, Path | None]
        ] = {}  # Temp storage for include source maps

    def _convert_key_to_string(self, key: Any) -> Any:
        """
        Convert date and numeric keys to strings.

        Args:
            key: Key to convert

        Returns:
            Converted key (string if date/numeric, otherwise unchanged)
        """
        if isinstance(key, datetime.date):
            return str(key)
        elif not isinstance(key, bool) and isinstance(key, (int, float)):
            return str(key)
        return key

    def _convert_mapping_keys(self, mapping: dict) -> dict:
        """
        Convert all date and numeric keys in a mapping to strings.

        Args:
            mapping: Mapping to process

        Returns:
            Mapping with converted keys
        """
        for key in list(mapping.keys()):
            converted_key = self._convert_key_to_string(key)
            if converted_key != key:
                mapping[converted_key] = mapping.pop(key)
        return mapping

    def _build_config_path(self, key: str) -> str:
        """
        Build full config path from current stack and key.

        Args:
            key: Current key

        Returns:
            Full dotted path (e.g., "section.subsection.key")
        """
        if self._path_stack:
            return ".".join(self._path_stack + [str(key)])
        return str(key)

    def _construct_value_with_tracking(
        self, value_node: yaml.Node, full_path: str
    ) -> Any:
        """
        Construct value from node and track sources for lists.

        Args:
            value_node: YAML node to construct
            full_path: Full config path for this value

        Returns:
            Constructed value
        """
        if isinstance(value_node, yaml.MappingNode):
            # Push key onto stack for nested mappings
            key = full_path.split(".")[-1]
            self._path_stack.append(key)
            value = self.construct_object(value_node, deep=True)
            self._path_stack.pop()
            return value

        elif isinstance(value_node, yaml.SequenceNode):
            # Track list items with indexed paths
            value = self.construct_sequence(value_node, deep=True)
            for idx in range(len(value)):
                item_path = f"{full_path}[{idx}]"
                self.source_map[item_path] = self.current_file
            return value

        else:
            # Scalar or !include tag
            return self.construct_object(value_node, deep=True)

    def _merge_include_source_maps(self, value: Any, full_path: str) -> None:
        """
        Merge pending include source maps into main source map.

        Args:
            value: Value that might have come from an include
            full_path: Full config path where this value is located
        """
        value_id = id(value)
        if value_id in self._pending_include_maps:
            included_map = self._pending_include_maps.pop(value_id)
            for inc_key, inc_source in included_map.items():
                prefixed_key = f"{full_path}.{inc_key}"
                self.source_map[prefixed_key] = inc_source

    def _should_use_simple_construction(self, node: Any) -> bool:
        """Check if simple construction should be used (non-tracking mode or test data)."""
        # Non-tracking mode or missing node value
        if not self.track_sources or not hasattr(node, "value") or not node.value:
            return True

        # Test data check (not real YAML nodes)
        first_item = node.value[0] if node.value else None
        if first_item and not isinstance(first_item[0], yaml.Node):
            return True

        return False

    def _process_mapping_key_value(
        self, key_node: Any, value_node: Any
    ) -> tuple[Any, Any]:
        """Process a single key-value pair with source tracking."""
        # Construct and convert key
        key = self.construct_object(key_node, deep=False)
        key = self._convert_key_to_string(key)

        # Build full path and record source
        full_path = self._build_config_path(key)
        self.source_map[full_path] = self.current_file

        # Construct value with proper tracking
        value = self._construct_value_with_tracking(value_node, full_path)

        # Merge any included source maps
        self._merge_include_source_maps(value, full_path)

        return key, value

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[str, Any]:
        """
        Construct a mapping with automatic key conversion and source tracking.

        Converts date and numeric keys to strings to ensure consistent
        key types in the resulting mapping. Optionally tracks source file
        for each key-value pair.

        Args:
            node: YAML node to construct
            deep: Whether to construct nested structures deeply

        Returns:
            dict: Mapping with converted keys
        """
        # Use simple construction for non-tracking mode or test data
        if self._should_use_simple_construction(node):
            mapping = super().construct_mapping(node, deep=deep)
            return self._convert_mapping_keys(mapping)

        # Real YAML parsing with source tracking
        mapping = {}
        for key_node, value_node in node.value:
            key, value = self._process_mapping_key_value(key_node, value_node)
            mapping[key] = value

        return mapping

    def _resolve_include_path(self, include_path_str: str) -> Path:
        """
        Resolve include path to absolute path.

        Args:
            include_path_str: Path string from !include tag

        Returns:
            Resolved absolute path

        Raises:
            yaml.YAMLError: If relative path cannot be resolved
        """
        include_path = Path(include_path_str)

        if not include_path.is_absolute():
            # Relative path - resolve from current file's directory
            if self.current_file is None:
                raise yaml.YAMLError(
                    f"Cannot resolve relative include path '{include_path_str}' "
                    "without a current file context"
                )
            return (self.current_file.parent / include_path).resolve()

        return include_path.resolve()

    def _validate_include(self, include_path: Path) -> None:
        """
        Validate include path for circular dependencies, existence, and security.

        Args:
            include_path: Path to validate

        Raises:
            yaml.YAMLError: If circular include detected, file not found, or path traversal detected
        """
        # Check for circular includes
        if include_path in self.include_chain:
            chain_str = " -> ".join(str(f) for f in self.include_chain)
            raise yaml.YAMLError(
                f"Circular include detected: {chain_str} -> {include_path}"
            )

        # Check if file exists
        try:
            file_exists = include_path.exists()
        except (PermissionError, OSError):
            # If we can't check existence due to permissions, treat as not found
            raise yaml.YAMLError(f"Include file not found: {include_path}")

        if not file_exists:
            raise yaml.YAMLError(f"Include file not found: {include_path}")

        # Security: Validate path stays within project root if specified
        if self.project_root is not None:
            try:
                # is_relative_to() raises ValueError if not relative (Python 3.9+)
                # Use try/except for compatibility
                include_path.relative_to(self.project_root)
            except (ValueError, TypeError):
                raise yaml.YAMLError(
                    f"Security: Include path '{include_path}' is outside project root '{self.project_root}'. "
                    f"This could be a path traversal attack."
                )

    def _load_included_file(self, include_path: Path) -> Any:
        """
        Load and parse included YAML file.

        Args:
            include_path: Path to the included file

        Returns:
            Parsed data from included file

        Raises:
            yaml.YAMLError: If include depth exceeds max_include_depth
        """
        new_chain = self.include_chain | {include_path}

        # Security: Check include depth to prevent stack overflow
        if len(new_chain) > self.max_include_depth:
            raise yaml.YAMLError(
                f"Include depth exceeds maximum of {self.max_include_depth}. "
                f"This could indicate a deeply nested include or recursive include pattern. "
                f"Include chain: {' -> '.join(str(p) for p in new_chain)}"
            )

        with open(include_path) as f:
            included_loader = Loader(
                f,
                current_file=include_path,
                include_chain=new_chain,
                merge_strategy=self.merge_strategy,
                track_sources=self.track_sources,
                project_root=self.project_root,
                max_include_depth=self.max_include_depth,
            )
            included_data = included_loader.get_single_data()

            # Store source map for later merging
            if self.track_sources and hasattr(included_loader, "source_map"):
                self._pending_include_maps[id(included_data)] = (
                    included_loader.source_map
                )

        return included_data

    def _extract_section_from_data(self, data: Any, section_path: str) -> Any:
        """
        Extract a specific section from loaded data using dot notation.

        Args:
            data: Loaded YAML data (typically a dict)
            section_path: Dot-separated path to section (e.g., "pgserver" or "database.postgres")

        Returns:
            Data at the specified section path

        Raises:
            yaml.YAMLError: If section path is invalid or not found
        """
        if not section_path:
            return data

        current = data
        parts = section_path.split(".")

        for i, part in enumerate(parts):
            if not isinstance(current, dict):
                traversed = ".".join(parts[:i])
                raise yaml.YAMLError(
                    f"Cannot navigate to '{section_path}': "
                    f"'{traversed}' is not a mapping (got {type(current).__name__})"
                )

            if part not in current:
                raise yaml.YAMLError(
                    f"Section '{section_path}' not found in included file. "
                    f"Available keys at this level: {list(current.keys())}"
                )

            current = current[part]

        return current

    def include_constructor(self, node: Any) -> Any:
        """
        Construct included content from !include tag.

        Supports:
        - Relative paths (resolved from current file's directory)
        - Absolute paths
        - Circular dependency detection
        - Recursive includes
        - Section anchors (e.g., "config.yaml#database.postgres")

        Args:
            node: YAML node containing the include path

        Returns:
            Content from the included file (or specific section if anchor specified)

        Raises:
            yaml.YAMLError: If circular include detected, file not found, or section not found

        Examples:
            !include "database.yaml"              # Include entire file
            !include "config.yaml#database"       # Include only 'database' section
            !include "config.yaml#app.settings"   # Include nested 'app.settings' section
        """
        # Parse include path and optional section anchor
        include_spec = self.construct_scalar(node)

        # Split on '#' to separate file path from section path
        if "#" in include_spec:
            include_path_str, section_path = include_spec.split("#", 1)
        else:
            include_path_str = include_spec
            section_path = ""

        # Simple pipeline: resolve → validate → load → extract section
        include_path = self._resolve_include_path(include_path_str)
        self._validate_include(include_path)
        data = self._load_included_file(include_path)

        # Extract specific section if requested
        if section_path:
            return self._extract_section_from_data(data, section_path)

        return data

    def secret_constructor(self, node: Any) -> str:
        """
        Construct value from !secret tag with validation.

        Validates that secret values use environment variable syntax ${VAR_NAME}.
        Emits SecurityWarning if a literal value is detected.

        Args:
            node: YAML node containing the secret value

        Returns:
            The secret value string (env var reference or literal)

        Example:
            password: !secret ${DB_PASSWORD}    # Valid - env var syntax
            api_key: !secret my_actual_key      # Warning - literal value
        """
        value: str = self.construct_scalar(node)

        if not ENV_VAR_PATTERN.match(value):
            # Truncate for security - don't log full secret in warning
            display_value = value[:20] + "..." if len(value) > 20 else value
            warnings.warn(
                f"Secret value appears to be a literal instead of env var reference. "
                f"Use ${{VAR_NAME}} syntax. Found: {display_value}",
                SecretLiteralWarning,
                stacklevel=6,  # Point to YAML load call site
            )

        return value

    def path_constructor(self, node: Any) -> str:
        """
        Construct resolved path from !path tag.

        Expands ~ to home directory and resolves relative paths from the
        current file's directory. Returns the resolved path as a string.

        Args:
            node: YAML node containing the path

        Returns:
            Resolved absolute path as string

        Raises:
            yaml.YAMLError: If relative path cannot be resolved without file context

        Example:
            models_dir: !path ../.models          # Resolves relative to config file
            data_dir: !path /absolute/path        # Absolute paths unchanged
            home_dir: !path ~/data                # Expands ~ to home directory
        """
        path_str: str = self.construct_scalar(node)
        path = Path(path_str).expanduser()

        if not path.is_absolute():
            if self.current_file is None:
                raise yaml.YAMLError(
                    f"Cannot resolve relative path '{path_str}' without a current file context"
                )
            path = (self.current_file.parent / path).resolve()
        else:
            path = path.resolve()

        return str(path)


# Register tag constructors with the Loader class
Loader.add_constructor("!include", Loader.include_constructor)
Loader.add_constructor("!secret", Loader.secret_constructor)
Loader.add_constructor("!path", Loader.path_constructor)


def load(
    stream: Any,
    current_file: Path | None = None,
    merge_strategy: str = "replace",
    track_sources: bool = False,
    project_root: Path | None = None,
    max_include_depth: int = 10,
) -> Any | tuple[Any, dict[str, Path | None]]:
    """
    Load YAML with include support and optional source tracking.

    Args:
        stream: File object or string to load YAML from
        current_file: Path to the current file (for relative includes)
        merge_strategy: Strategy for merging includes - "replace" or "merge"
        track_sources: If True, return source file map for path resolution
        project_root: Optional project root to restrict includes (prevents path traversal attacks)
        max_include_depth: Maximum allowed depth for nested includes (default: 10)

    Returns:
        If track_sources is True: Tuple of (data, source_map)
        If track_sources is False: Just the data (for backward compatibility)

    Example:
        # Without source tracking (backward compatible)
        with open('config.yaml') as f:
            config = yaml_load(f, current_file=Path('config.yaml'))

        # With source tracking and security
        with open('config.yaml') as f:
            config, source_map = yaml_load(
                f,
                current_file=Path('config.yaml'),
                track_sources=True,
                project_root=Path('/path/to/project')
            )
    """
    loader = Loader(
        stream,
        current_file=current_file,
        merge_strategy=merge_strategy,
        track_sources=track_sources,
        project_root=project_root,
        max_include_depth=max_include_depth,
    )
    try:
        data = loader.get_single_data()
        if track_sources:
            return data, loader.source_map
        # For backward compatibility, return just data when not tracking sources
        return data
    finally:
        loader.dispose()
