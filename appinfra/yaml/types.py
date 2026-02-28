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


class DeepMergeWrapper:
    """
    Wrapper to mark data for deep merging with YAML merge keys (<<).

    When used with the !deep tag, signals that the wrapped data should be
    deep-merged into the parent mapping instead of shallow-merged.

    Example:
        templates:
          vllm_default: &vllm_default
            max_model_len: 8192
            vllm:
              enforce_eager: false
              max_num_seqs: 4

        models:
          my-model:
            <<: !deep *vllm_default
            vllm:
              gpu_memory_gb: 8.0   # Deep merged with template's vllm

    Result:
        my-model:
          max_model_len: 8192
          vllm:
            enforce_eager: false   # Preserved from template
            max_num_seqs: 4        # Preserved from template
            gpu_memory_gb: 8.0     # Added locally
    """

    __slots__ = ("data",)

    def __init__(self, data: dict) -> None:
        """
        Initialize wrapper with data to deep merge.

        Args:
            data: Dictionary data to be deep merged. Must be a dict.

        Raises:
            TypeError: If data is not a dictionary.
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"!deep tag requires a mapping (dict), got {type(data).__name__}. "
                "Use !deep with anchors or includes that resolve to mappings."
            )
        self.data = data

    def __repr__(self) -> str:
        return f"DeepMergeWrapper({self.data!r})"
