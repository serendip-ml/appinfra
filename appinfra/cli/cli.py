#!/usr/bin/env python3
"""
Infra CLI - Utility commands for the infra framework.

Usage:
    appinfra scaffold my-project --with-db
    appinfra scaffold my-api --with-db --with-server
    appinfra --help
"""

import sys
from importlib.resources import files
from pathlib import Path

# Add project root to path for running as script (before package is installed)
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import appinfra
from appinfra.app import App, AppBuilder


def _handle_path_commands() -> int | None:
    """Handle simple path commands without full app setup.

    These commands just print a path and don't need logging infrastructure.
    Early exit prevents log output from polluting stdout for Makefile usage.

    Returns:
        Exit code if handled, None if not a path command.
    """
    if len(sys.argv) >= 2:
        cmd = sys.argv[1]
        if cmd == "scripts-path":
            print(files("appinfra") / "scripts")
            return 0
        if cmd == "etc-path":
            if "--local" in sys.argv:
                from appinfra.app.core.config import resolve_etc_dir

                try:
                    print(resolve_etc_dir())
                except FileNotFoundError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    return 1
            else:
                print(files("appinfra") / "etc")
            return 0
    return None


from appinfra.cli.tools.code_quality import CodeQualityTool
from appinfra.cli.tools.completion_tool import CompletionTool
from appinfra.cli.tools.config_tool import ConfigTool
from appinfra.cli.tools.docs_tool import DocsTool
from appinfra.cli.tools.doctor_tool import DoctorTool
from appinfra.cli.tools.etc_path_tool import EtcPathTool
from appinfra.cli.tools.scaffold_tool import ScaffoldTool
from appinfra.cli.tools.scripts_path_tool import ScriptsPathTool

# All CLI tools
_TOOLS = [
    CodeQualityTool,
    CompletionTool,
    ConfigTool,
    DoctorTool,
    DocsTool,
    ScaffoldTool,
    ScriptsPathTool,
    EtcPathTool,
]


def _build_app() -> "App":
    """Build the CLI application with all tools registered."""
    builder = (
        AppBuilder("appinfra")
        .with_description("Infra framework utility commands")
        .with_version(appinfra.__version__)
        .without_standard_args()
        .with_standard_args(etc_dir=True, log_level=True, quiet=True)
    )
    for tool_cls in _TOOLS:
        builder = builder.tools.with_tool(tool_cls()).done()
    return (
        builder.advanced.with_argument(
            "-v",
            "--version",
            action="version",
            version=f"appinfra {appinfra.__version__}",
        )
        .done()
        .logging.with_level("info")
        .done()
        .build()
    )


def main() -> int:
    """Main entry point for infra CLI."""
    # Fast path for simple commands that don't need the full app framework
    result = _handle_path_commands()
    if result is not None:
        return result

    return _build_app().main()


if __name__ == "__main__":
    exit(main())
