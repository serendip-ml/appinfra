"""
Build info generator for git hooks.

Run this before commit to update _build_info.py in a package:

    python -m appinfra.version.build_info mypackage/

Or from a git pre-commit hook:

    #!/bin/sh
    python -m appinfra.version.build_info mypackage/
    git add mypackage/_build_info.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_TEMPLATE = '''\
"""Build information - auto-generated, do not edit."""

COMMIT_HASH = "{commit_full}"
COMMIT_SHORT = "{commit_short}"
COMMIT_MESSAGE = "{commit_message}"
BUILD_TIME = "{build_time}"
'''


def get_git_commit() -> tuple[str, str, str] | None:
    """Get current git commit hash and message."""
    try:
        # Get commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        full = result.stdout.strip()
        short = full[:7]

        # Get commit message (first line only)
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        message = result.stdout.strip() if result.returncode == 0 else ""

        return full, short, message
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return None


def generate(package_dir: Path) -> bool:
    """
    Generate _build_info.py in the given package directory.

    Args:
        package_dir: Path to the package directory

    Returns:
        True if successful, False otherwise
    """
    commit = get_git_commit()
    if not commit:
        print("Not in a git repo or no commits", file=sys.stderr)
        return False

    commit_full, commit_short, commit_message = commit
    build_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Escape message for Python string
    escaped_message = commit_message.replace("\\", "\\\\").replace('"', '\\"')

    content = _TEMPLATE.format(
        commit_full=commit_full,
        commit_short=commit_short,
        commit_message=escaped_message,
        build_time=build_time,
    )

    build_info_path = package_dir / "_build_info.py"
    build_info_path.write_text(content)
    print(f"Generated {build_info_path}")
    return True


def main() -> int:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m appinfra.version.build_info <package_dir>")
        return 1

    package_dir = Path(sys.argv[1])
    if not package_dir.is_dir():
        print(f"Not a directory: {package_dir}", file=sys.stderr)
        return 1

    return 0 if generate(package_dir) else 1


if __name__ == "__main__":
    sys.exit(main())
