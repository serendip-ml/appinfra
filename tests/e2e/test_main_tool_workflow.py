"""
E2E tests for with_main_tool() workflow.

Tests the complete workflow for single-tool apps where the main tool
runs without requiring a subcommand.

Example:
    ./proxy.py --port 8080        # Main tool runs automatically
    ./proxy.py run --port 8080    # Explicit subcommand still works
"""

import sys
from unittest.mock import patch

import pytest

from appinfra.app.builder import AppBuilder
from appinfra.app.tools import Tool, ToolConfig


class ProxyTool(Tool):
    """Test tool simulating a proxy server."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            ToolConfig(name="run", aliases=["r"], help_text="Run the proxy server"),
        )
        self.captured_port = None
        self.captured_host = None
        self.run_called = False

    def add_args(self, parser):
        parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
        parser.add_argument("--host", default="localhost", help="Host to bind to")

    def run(self, **kwargs):
        self.run_called = True
        self.captured_port = self.args.port
        self.captured_host = self.args.host
        return 0


@pytest.mark.e2e
class TestMainToolWorkflow:
    """E2E tests for with_main_tool() feature."""

    def test_main_tool_runs_without_subcommand(self):
        """Test that main tool runs when no subcommand is specified."""
        tool = ProxyTool()
        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Invoke without subcommand - just tool args
        with patch.object(sys, "argv", ["proxy", "--port", "9000"]):
            app.setup()
            result = app.run()

        assert tool.run_called
        assert tool.captured_port == 9000
        assert result == 0

    def test_main_tool_with_explicit_subcommand_still_works(self):
        """Test that explicit subcommand still works with main tool set."""
        tool = ProxyTool()
        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Invoke with explicit subcommand
        with patch.object(sys, "argv", ["proxy", "run", "--port", "7000"]):
            app.setup()
            result = app.run()

        assert tool.run_called
        assert tool.captured_port == 7000
        assert result == 0

    def test_main_tool_uses_default_args_when_none_provided(self):
        """Test that main tool uses default arg values when none specified."""
        tool = ProxyTool()
        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Invoke with no args at all
        with patch.object(sys, "argv", ["proxy"]):
            app.setup()
            result = app.run()

        assert tool.run_called
        assert tool.captured_port == 8080  # default
        assert tool.captured_host == "localhost"  # default
        assert result == 0

    def test_main_tool_with_multiple_tools(self):
        """Test main tool works correctly when multiple tools are registered."""

        class OtherTool(Tool):
            def __init__(self, parent=None):
                super().__init__(
                    parent,
                    ToolConfig(name="other", help_text="Other tool"),
                )
                self.run_called = False

            def run(self, **kwargs):
                self.run_called = True
                return 0

        main_tool = ProxyTool()
        other_tool = OtherTool()

        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(main_tool)
            .with_tool(other_tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Without subcommand - main tool runs
        with patch.object(sys, "argv", ["proxy", "--port", "5000"]):
            app.setup()
            app.run()

        assert main_tool.run_called
        assert main_tool.captured_port == 5000
        assert not other_tool.run_called

    def test_explicit_other_tool_runs_instead_of_main(self):
        """Test that explicitly specifying another tool runs that tool."""

        class OtherTool(Tool):
            def __init__(self, parent=None):
                super().__init__(
                    parent,
                    ToolConfig(name="other", help_text="Other tool"),
                )
                self.run_called = False

            def run(self, **kwargs):
                self.run_called = True
                return 42

        main_tool = ProxyTool()
        other_tool = OtherTool()

        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(main_tool)
            .with_tool(other_tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Explicitly run "other" tool
        with patch.object(sys, "argv", ["proxy", "other"]):
            app.setup()
            result = app.run()

        assert other_tool.run_called
        assert not main_tool.run_called
        assert result == 42

    def test_main_tool_with_tool_object(self):
        """Test with_main_tool() accepts Tool object, not just string."""
        tool = ProxyTool()
        app = (
            AppBuilder("proxy")
            .without_standard_args()
            .tools.with_tool(tool)
            .done()
            .with_main_tool(tool)  # Pass Tool object
            .build()
        )

        with patch.object(sys, "argv", ["proxy", "--port", "3000"]):
            app.setup()
            result = app.run()

        assert tool.run_called
        assert tool.captured_port == 3000
        assert result == 0

    def test_main_tool_with_standard_args(self):
        """Test main tool works alongside standard args like --log-level."""
        tool = ProxyTool()
        app = (
            AppBuilder("proxy")
            .tools.with_tool(tool)
            .done()
            .with_main_tool("run")
            .build()
        )

        # Mix standard args with tool args
        with patch.object(
            sys, "argv", ["proxy", "--log-level", "debug", "--port", "4000"]
        ):
            app.setup()
            result = app.run()

        assert tool.run_called
        assert tool.captured_port == 4000
        assert app.config.logging.level == "debug"
        assert result == 0
