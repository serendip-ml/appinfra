"""
Type definitions, patterns, and warning classes for YAML processing.

This module contains:
- ErrorContext and IncludeContext dataclasses for error reporting
- Regex patterns for environment variables and document includes
- SecretLiteralWarning for !secret tag validation
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ErrorContext:
    """Context for YAML error reporting with file location information."""

    current_file: Path | None = None
    line: int | None = None
    column: int | None = None

    def format_location(self) -> str:
        """Format file and position for error messages."""
        parts = []
        if self.current_file:
            parts.append(f"in '{self.current_file}'")
        if self.line is not None:
            # YAML lines are 0-indexed, display as 1-indexed
            parts.append(f"line {self.line + 1}")
        if self.column is not None:
            parts.append(f"column {self.column + 1}")
        return ", ".join(parts) if parts else "unknown location"


@dataclass(frozen=True)
class IncludeContext(ErrorContext):
    """Extended context for !include directive processing."""

    include_chain: frozenset[Path] = frozenset()
    project_root: Path | None = None
    max_include_depth: int = 10


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
