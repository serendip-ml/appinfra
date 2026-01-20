"""
Custom YAML loader with enhanced key handling and include support.

This module provides a custom YAML loader that automatically converts
certain key types to strings for better compatibility and supports
file inclusion via the !include tag and secrets validation via !secret tag.
"""

import datetime
import re
import warnings
from collections.abc import Hashable
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

# Pattern for environment variable references: ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

# Pattern for document-level !include directives (at column 0)
# Matches: !include "./path.yaml" or !include './path.yaml' or !include path.yaml
# Optionally with section anchor: !include "./path.yaml#section"
# Optionally with trailing comment: !include "./path.yaml"  # comment
DOCUMENT_INCLUDE_PATTERN = re.compile(
    r"^!include\s+"
    r'(?:"([^"]+)"|\'([^\']+)\'|(\S+?))'  # Quoted or unquoted path
    r"\s*(?:#.*)?$"  # Optional trailing comment
)


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


def _preprocess_document_includes(content: str) -> tuple[str, list[str]]:
    """
    Extract document-level !include directives from YAML content.

    Document-level includes are !include tags at column 0 (no indentation)
    that should be merged with the rest of the document. This preprocessing
    step is necessary because YAML parses !include as a tagged scalar, which
    cannot coexist with other root-level content without a document separator.

    Args:
        content: Raw YAML content

    Returns:
        Tuple of (remaining_content, list_of_include_paths)

    Example:
        Input:
            !include "./base.yaml"

            name: app
            server:
              port: 8080

        Output:
            ('\\nname: app\\nserver:\\n  port: 8080', ['./base.yaml'])
    """
    lines = content.splitlines(keepends=True)
    include_paths: list[str] = []
    remaining_lines: list[str] = []

    for line in lines:
        # Only check non-indented lines (document level)
        stripped = line.lstrip()
        if line == stripped:  # No leading whitespace = document level
            match = DOCUMENT_INCLUDE_PATTERN.match(line.rstrip())
            if match:
                # Extract path from whichever group matched (double-quoted, single-quoted, or unquoted)
                path = match.group(1) or match.group(2) or match.group(3)
                if path:
                    include_paths.append(path)
                continue  # Don't add this line to remaining content

        remaining_lines.append(line)

    return "".join(remaining_lines), include_paths


def _resolve_include_path_standalone(
    include_path_str: str,
    current_file: Path | None,
) -> Path:
    """
    Resolve include path to absolute path (standalone version for preprocessing).

    Args:
        include_path_str: Path string from !include directive
        current_file: Path to current file (for relative path resolution)

    Returns:
        Resolved absolute path

    Raises:
        yaml.YAMLError: If relative path cannot be resolved
    """
    include_path = Path(include_path_str)

    if not include_path.is_absolute():
        if current_file is None:
            raise yaml.YAMLError(
                f"Cannot resolve relative include path '{include_path_str}' "
                "without a current file context"
            )
        return (current_file.parent / include_path).resolve()

    return include_path.resolve()


def _check_circular_include(include_path: Path, include_chain: set[Path]) -> None:
    """Raise error if circular include detected."""
    if include_path in include_chain:
        chain_str = " -> ".join(str(f) for f in include_chain)
        raise yaml.YAMLError(
            f"Circular include detected: {chain_str} -> {include_path}"
        )


def _check_include_depth(
    include_path: Path, include_chain: set[Path], max_depth: int
) -> None:
    """Raise error if include depth exceeds maximum."""
    if len(include_chain) + 1 > max_depth:
        chain_str = " -> ".join(str(f) for f in include_chain)
        msg = (
            f"Include depth exceeds maximum of {max_depth}. "
            f"This could indicate a deeply nested include or recursive include pattern. "
            f"Include chain: {chain_str} -> {include_path}"
        )
        raise yaml.YAMLError(msg)


def _check_file_exists(include_path: Path) -> None:
    """Raise error if include file doesn't exist."""
    try:
        if not include_path.exists():
            raise yaml.YAMLError(f"Include file not found: {include_path}")
    except (PermissionError, OSError) as e:
        raise yaml.YAMLError(f"Include file not found: {include_path}") from e


def _check_project_root(include_path: Path, project_root: Path | None) -> None:
    """Raise error if path is outside project root."""
    if project_root is None:
        return
    try:
        include_path.relative_to(project_root)
    except (ValueError, TypeError) as e:
        msg = (
            f"Security: Include path '{include_path}' is outside project root "
            f"'{project_root}'. This could be a path traversal attack."
        )
        raise yaml.YAMLError(msg) from e


def _validate_include_standalone(
    include_path: Path,
    include_chain: set[Path],
    project_root: Path | None,
    max_include_depth: int,
) -> None:
    """Validate include path for circular dependencies, existence, and security."""
    _check_circular_include(include_path, include_chain)
    _check_include_depth(include_path, include_chain, max_include_depth)
    _check_file_exists(include_path)
    _check_project_root(include_path, project_root)


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

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Hashable, Any]:
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

        # Handle YAML merge keys (<<: *anchor) before processing.
        # flatten_mapping expands merge keys into regular key-value pairs.
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)

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


def _extract_section_data(
    data: Any,
    section_path: str,
    include_path: Path,
) -> Any:
    """
    Extract a specific section from data using dot-notation path.

    Args:
        data: Data to extract from
        section_path: Dot-separated path (e.g., "server.http")
        include_path: Path to included file (for error messages)

    Returns:
        Data at the specified section path

    Raises:
        yaml.YAMLError: If section path is invalid or not found
    """
    current = data
    parts = section_path.split(".")

    for i, part in enumerate(parts):
        if not isinstance(current, dict):
            traversed = ".".join(parts[:i])
            msg = (
                f"Cannot navigate to '{section_path}': "
                f"'{traversed}' is not a mapping (got {type(current).__name__})"
            )
            raise yaml.YAMLError(msg)
        if part not in current:
            msg = (
                f"Section '{section_path}' not found in included file '{include_path}'. "
                f"Available keys at this level: {list(current.keys())}"
            )
            raise yaml.YAMLError(msg)
        current = current[part]

    return current


def _filter_source_map_for_section(
    source_map: dict[str, Path | None],
    section_path: str,
) -> dict[str, Path | None]:
    """
    Filter source map to only include keys under the section path.

    Args:
        source_map: Original source map
        section_path: Section path that was extracted

    Returns:
        Filtered source map with section prefix removed from keys
    """
    prefix = section_path + "."
    filtered_map: dict[str, Path | None] = {}

    for key, source in source_map.items():
        if key.startswith(prefix):
            new_key = key[len(prefix) :]
            filtered_map[new_key] = source
        elif key == section_path:
            filtered_map[""] = source

    return filtered_map


def _load_document_include(
    include_spec: str,
    current_file: Path | None,
    include_chain: set[Path],
    merge_strategy: str,
    track_sources: bool,
    project_root: Path | None,
    max_include_depth: int,
) -> tuple[Any, dict[str, Path | None]]:
    """
    Load a document-level include file with section extraction support.

    Args:
        include_spec: Include path, optionally with section anchor (e.g., "file.yaml#section")
        current_file: Path to current file (for relative path resolution)
        include_chain: Set of files in current include chain
        merge_strategy: Strategy for merging includes
        track_sources: If True, track source files
        project_root: Optional project root for security validation
        max_include_depth: Maximum allowed include depth

    Returns:
        Tuple of (data, source_map)
    """
    # Parse include path and optional section anchor
    include_path_str, section_path = (
        include_spec.split("#", 1) if "#" in include_spec else (include_spec, "")
    )

    # Resolve and validate path
    resolved_project_root = project_root.resolve() if project_root else None
    include_path = _resolve_include_path_standalone(include_path_str, current_file)
    _validate_include_standalone(
        include_path, include_chain, resolved_project_root, max_include_depth
    )

    # Load the included file recursively
    data, source_map = _load_include_file(
        include_path,
        include_chain,
        merge_strategy,
        track_sources,
        project_root,
        max_include_depth,
    )

    # Extract section if specified
    if section_path and data is not None:
        data = _extract_section_data(data, section_path, include_path)
        if track_sources:
            source_map = _filter_source_map_for_section(source_map, section_path)

    return data, source_map


def _load_include_file(
    include_path: Path,
    include_chain: set[Path],
    merge_strategy: str,
    track_sources: bool,
    project_root: Path | None,
    max_include_depth: int,
) -> tuple[Any, dict[str, Path | None]]:
    """
    Load an included YAML file.

    Args:
        include_path: Resolved path to the included file
        include_chain: Current include chain for circular detection
        merge_strategy: Strategy for merging includes
        track_sources: If True, track source files
        project_root: Optional project root for security validation
        max_include_depth: Maximum allowed include depth

    Returns:
        Tuple of (data, source_map)
    """
    new_chain = include_chain | {include_path}
    with open(include_path) as f:
        result = load(
            f,
            current_file=include_path,
            merge_strategy=merge_strategy,
            track_sources=track_sources,
            project_root=project_root,
            max_include_depth=max_include_depth,
            _include_chain=new_chain,
        )

    if track_sources:
        return result  # type: ignore[return-value]
    return result, {}


def _merge_document_includes(
    doc_include_paths: list[str],
    current_file: Path | None,
    include_chain: set[Path],
    merge_strategy: str,
    track_sources: bool,
    project_root: Path | None,
    max_include_depth: int,
) -> tuple[dict[str, Any] | None, dict[str, Path | None]]:
    """
    Load and merge all document-level includes.

    Args:
        doc_include_paths: List of include paths from preprocessing
        current_file: Path to current file for relative path resolution
        include_chain: Current include chain for circular detection
        merge_strategy: Strategy for merging includes
        track_sources: If True, track source files
        project_root: Optional project root for security validation
        max_include_depth: Maximum allowed include depth

    Returns:
        Tuple of (merged_data, merged_source_map)
    """
    merged_data: dict[str, Any] | None = None
    merged_source_map: dict[str, Path | None] = {}

    for include_spec in doc_include_paths:
        include_data, include_source_map = _load_document_include(
            include_spec,
            current_file,
            include_chain,
            merge_strategy,
            track_sources,
            project_root,
            max_include_depth,
        )

        if include_data is not None:
            if merged_data is None:
                merged_data = include_data if isinstance(include_data, dict) else {}
            elif isinstance(include_data, dict):
                merged_data = deep_merge(merged_data, include_data)

            if track_sources:
                merged_source_map.update(include_source_map)

    return merged_data, merged_source_map


def _parse_yaml_content(
    content: str,
    current_file: Path | None,
    include_chain: set[Path],
    merge_strategy: str,
    track_sources: bool,
    project_root: Path | None,
    max_include_depth: int,
) -> tuple[Any, dict[str, Path | None]]:
    """
    Parse YAML content using the Loader.

    Args:
        content: YAML content string to parse
        current_file: Path to current file for relative path resolution
        include_chain: Current include chain for circular detection
        merge_strategy: Strategy for merging includes
        track_sources: If True, track source files
        project_root: Optional project root for security validation
        max_include_depth: Maximum allowed include depth

    Returns:
        Tuple of (data, source_map)
    """
    from io import StringIO

    loader = Loader(
        StringIO(content),
        current_file=current_file,
        include_chain=include_chain,
        merge_strategy=merge_strategy,
        track_sources=track_sources,
        project_root=project_root.resolve() if project_root else None,
        max_include_depth=max_include_depth,
    )
    try:
        data = loader.get_single_data()
        source_map = loader.source_map if track_sources else {}
        return data, source_map
    finally:
        loader.dispose()


def _merge_data_and_sources(
    merged_data: dict[str, Any] | None,
    main_data: Any,
    merged_source_map: dict[str, Path | None],
    main_source_map: dict[str, Path | None],
) -> tuple[Any, dict[str, Path | None]]:
    """
    Merge document-level includes with main document data.

    Document-level includes provide defaults; main document overrides.

    Args:
        merged_data: Data merged from document-level includes
        main_data: Data from the main document
        merged_source_map: Source map from document-level includes
        main_source_map: Source map from main document

    Returns:
        Tuple of (final_data, final_source_map)
    """
    if merged_data is not None and main_data is not None:
        if isinstance(main_data, dict):
            final_data = deep_merge(merged_data, main_data)
        else:
            final_data = main_data  # Non-dict takes full precedence
    elif merged_data is not None:
        final_data = merged_data
    else:
        final_data = main_data

    final_source_map = {**merged_source_map, **main_source_map}
    return final_data, final_source_map


def _init_include_chain(
    current_file: Path | None, _include_chain: set[Path] | None
) -> set[Path]:
    """Initialize include chain, adding current file if provided."""
    chain = _include_chain if _include_chain is not None else set()
    if current_file is not None:
        chain = chain | {current_file.resolve()}
    return chain


def load(
    stream: Any,
    current_file: Path | None = None,
    merge_strategy: str = "replace",
    track_sources: bool = False,
    project_root: Path | None = None,
    max_include_depth: int = 10,
    _include_chain: set[Path] | None = None,
) -> Any | tuple[Any, dict[str, Path | None]]:
    """
    Load YAML with include support and optional source tracking.

    Supports key-level includes (`database: !include "db.yaml"`) and document-level
    includes (`!include "./base.yaml"` at line start). Document-level includes provide
    defaults; main document content overrides.

    Args:
        stream: File object or string to load YAML from
        current_file: Path to current file (for relative includes)
        merge_strategy: Strategy for merging - "replace" or "merge"
        track_sources: If True, return (data, source_map) tuple
        project_root: Restrict includes to this directory
        max_include_depth: Max nested include depth (default: 10)
    """
    include_chain = _init_include_chain(current_file, _include_chain)
    content = stream.read() if hasattr(stream, "read") else str(stream)
    remaining_content, doc_include_paths = _preprocess_document_includes(content)

    merged_data, merged_source_map = _merge_document_includes(
        doc_include_paths,
        current_file,
        include_chain,
        merge_strategy,
        track_sources,
        project_root,
        max_include_depth,
    )
    main_data, main_source_map = _parse_yaml_content(
        remaining_content,
        current_file,
        include_chain,
        merge_strategy,
        track_sources,
        project_root,
        max_include_depth,
    )
    final_data, final_source_map = _merge_data_and_sources(
        merged_data, main_data, merged_source_map, main_source_map
    )

    return (final_data, final_source_map) if track_sources else final_data
