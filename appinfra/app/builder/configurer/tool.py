"""
Tool configuration builder for AppBuilder.

This module provides focused builder for configuring tools, commands, and plugins.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...tools.base import Tool
from ..plugin import Plugin
from ..tool import ToolBuilder

if TYPE_CHECKING:
    from ..app import AppBuilder


class ToolConfigurer:
    """
    Focused builder for tool, command, and plugin configuration.

    This class extracts tool-related configuration from AppBuilder,
    following the Single Responsibility Principle.
    """

    def __init__(self, app_builder: "AppBuilder"):
        """
        Initialize the tool configurer.

        Args:
            app_builder: Parent AppBuilder instance
        """
        self._app_builder = app_builder

    def with_tool(self, tool: Tool) -> "ToolConfigurer":
        """
        Add a single tool to the application.

        Args:
            tool: Tool instance to add

        Returns:
            Self for method chaining
        """
        self._app_builder._tools.append(tool)
        return self

    def with_tools(self, *tools: Tool) -> "ToolConfigurer":
        """
        Add multiple tools to the application.

        Args:
            *tools: Variable number of Tool instances

        Returns:
            Self for method chaining
        """
        self._app_builder._tools.extend(tools)
        return self

    def with_tool_builder(self, builder: ToolBuilder) -> "ToolConfigurer":
        """
        Add a tool using a tool builder.

        Args:
            builder: ToolBuilder instance

        Returns:
            Self for method chaining
        """
        self._app_builder._tools.append(builder.build())
        return self

    def with_cmd(
        self,
        name: str,
        run_func: Callable,
        aliases: list[str] | None = None,
        help_text: str = "",
    ) -> "ToolConfigurer":
        """
        Add a command with a run function.

        Args:
            name: Command name
            run_func: Function to execute when command is called
            aliases: List of command aliases (optional)
            help_text: Help text for the command (optional)

        Returns:
            Self for method chaining
        """
        from ..app import Command

        command = Command(
            name=name, run_func=run_func, aliases=aliases or [], help_text=help_text
        )
        self._app_builder._commands.append(command)
        return self

    def with_plugin(self, plugin: Plugin) -> "ToolConfigurer":
        """
        Add a plugin to the application.

        Args:
            plugin: Plugin instance

        Returns:
            Self for method chaining
        """
        self._app_builder._plugins.register_plugin(plugin)
        return self

    def with_plugins(self, *plugins: Plugin) -> "ToolConfigurer":
        """
        Add multiple plugins to the application.

        Args:
            *plugins: Variable number of Plugin instances

        Returns:
            Self for method chaining
        """
        for plugin in plugins:
            self._app_builder._plugins.register_plugin(plugin)
        return self

    def done(self) -> "AppBuilder":
        """
        Finish tool configuration and return to main builder.

        Returns:
            Parent AppBuilder instance for continued chaining
        """
        return self._app_builder
