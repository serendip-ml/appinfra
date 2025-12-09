#!/usr/bin/env python3
"""
Infra CLI - Utility commands for the infra framework.

Usage:
    appinfra scaffold my-project --with-db
    appinfra scaffold my-api --with-db --with-server
    appinfra --help
"""

import sys
from pathlib import Path

# Add project root to path for running as script (before package is installed)
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import appinfra
from appinfra.app import AppBuilder
from appinfra.cli.tools.code_quality import CodeQualityTool
from appinfra.cli.tools.completion_tool import CompletionTool
from appinfra.cli.tools.config_tool import ConfigTool
from appinfra.cli.tools.docs_tool import DocsTool
from appinfra.cli.tools.doctor_tool import DoctorTool
from appinfra.cli.tools.scaffold_tool import ScaffoldTool


def main() -> int:
    """Main entry point for infra CLI."""
    app = (
        AppBuilder("appinfra")
        .with_description("Infra framework utility commands")
        .with_version(appinfra.__version__)
        .without_standard_args()
        .with_standard_args(etc_dir=True, log_level=True, quiet=True)
        .tools.with_tool(CodeQualityTool())
        .with_tool(CompletionTool())
        .with_tool(ConfigTool())
        .with_tool(DoctorTool())
        .with_tool(DocsTool())
        .with_tool(ScaffoldTool())
        .done()
        .advanced.with_argument(
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

    return app.main()


if __name__ == "__main__":
    exit(main())
