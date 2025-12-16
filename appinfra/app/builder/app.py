"""
Main AppBuilder class for constructing CLI applications.

This module provides the core AppBuilder class that orchestrates
the construction of applications using a fluent API.

The AppBuilder has been refactored to use focused configurers for better
maintainability and testability. Use .tools(), .server(), .logging(),
and .advanced() to access specialized configuration builders.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from appinfra.dot_dict import DotDict

from ..cfg import Config
from ..core.app import App
from ..decorators import DecoratorAPI
from ..server.handlers import Middleware
from ..tools.base import Tool, ToolConfig
from ..tracing.traceable import Traceable
from .config import ConfigBuilder, LoggingConfigBuilder, ServerConfigBuilder
from .configurer.advanced import AdvancedConfigurer
from .configurer.logging import LoggingConfigurer
from .configurer.server import ServerConfigurer
from .configurer.tool import ToolConfigurer
from .hook import HookBuilder, HookManager
from .middleware import MiddlewareBuilder
from .plugin import PluginManager
from .tool import ToolBuilder
from .validation import ValidationBuilder, ValidationRule

# Helper functions for AppBuilder.build()


def _create_base_app(main_cls: type | None, config: Any) -> App:
    """
    Create base application instance.

    Args:
        main_cls: Optional custom App subclass
        config: Application configuration

    Returns:
        App instance
    """
    return main_cls(config) if main_cls is not None else App(config)


def _set_app_metadata(
    app: App, name: str | None, description: str | None, version: str | None
) -> None:
    """
    Set application metadata (name, description, version).

    Args:
        app: App instance to configure
        name: Application name
        description: Application description
        version: Application version
    """
    if name:
        app.name = name  # type: ignore[attr-defined]
    if description:
        app.description = description  # type: ignore[attr-defined]
    if version:
        app.version = version  # type: ignore[attr-defined]


def _register_tools_and_commands(app: App, tools: list, commands: list) -> None:
    """
    Register tools and commands with application.

    Args:
        app: App instance
        tools: List of Tool instances
        commands: List of Command instances
    """
    for tool in tools:
        app.add_tool(tool)

    for command in commands:
        command_tool = CommandTool(command)
        app.add_tool(command_tool)


def _configure_middleware(app: App, middleware: list, server_config: Any) -> None:
    """
    Add middleware if server is configured.

    Args:
        app: App instance
        middleware: List of middleware
        server_config: Server configuration (None if no server)
    """
    if server_config:
        for mw in middleware:
            if hasattr(app, "add_middleware"):
                app.add_middleware(mw)


def _configure_arguments_and_validation(
    app: App, custom_args: list[tuple], validation_rules: list
) -> None:
    """
    Add custom arguments and validation rules.

    Args:
        app: App instance
        custom_args: List of (args, kwargs) tuples for add_argument
        validation_rules: List of validation rules
    """
    for args, kwargs in custom_args:
        if hasattr(app, "add_argument"):
            app.add_argument(*args, **kwargs)

    if hasattr(app, "add_validation_rule"):
        for rule in validation_rules:
            app.add_validation_rule(rule)


def _configure_hooks(app: App, hooks: Any) -> None:
    """
    Configure application hooks.

    Args:
        app: App instance
        hooks: HookManager instance
    """
    if hasattr(app, "set_hook_manager"):
        app.set_hook_manager(hooks)


def _configure_server_and_logging(
    app: App, server_config: Any, logging_config: Any
) -> None:
    """
    Configure server and logging if specified.

    Args:
        app: App instance
        server_config: Server configuration (optional)
        logging_config: Logging configuration (optional)
    """
    if server_config and hasattr(app, "configure_server"):
        app.configure_server(server_config)

    if logging_config and hasattr(app, "configure_logging"):
        app.configure_logging(logging_config)


def _register_lifecycle_managers(app: App, hooks: Any, plugins: Any) -> None:
    """
    Register component managers with lifecycle for shutdown coordination.

    Args:
        app: App instance
        hooks: HookManager instance (optional)
        plugins: PluginManager instance (optional)
    """
    if not hasattr(app, "lifecycle"):
        return

    lifecycle = app.lifecycle

    # Register hook manager
    if hooks and hasattr(lifecycle, "register_hook_manager"):
        lifecycle.register_hook_manager(hooks)

    # Register plugin manager
    if plugins and hasattr(lifecycle, "register_plugin_manager"):
        lifecycle.register_plugin_manager(plugins)

    # Register database manager if app has one
    if hasattr(app, "db") and hasattr(lifecycle, "register_db_manager"):
        lifecycle.register_db_manager(app.db)


def _initialize_foundation(app: App, builder: "AppBuilder") -> None:
    """Initialize app foundation: flags and metadata."""
    app._auto_load_config = builder._auto_load_config  # type: ignore[attr-defined]
    app._standard_args = builder._standard_args.copy()
    _set_app_metadata(app, builder._name, builder._description, builder._version)


def _register_components(app: App, builder: "AppBuilder") -> None:
    """Register all app components: tools, plugins, lifecycle."""
    _register_tools_and_commands(app, builder._tools, builder._commands)
    builder._plugins.configure_all(builder)
    _register_lifecycle_managers(app, builder._hooks, builder._plugins)
    _configure_arguments_and_validation(
        app, builder._custom_args, builder._validation_rules
    )


def _configure_external_services(app: App, builder: "AppBuilder") -> None:
    """Configure external services: server, logging, middleware, hooks."""
    _configure_middleware(app, builder._middleware, builder._server_config)
    _configure_hooks(app, builder._hooks)
    _configure_server_and_logging(app, builder._server_config, builder._logging_config)


@dataclass
class Command:
    """Represents a command with a run function."""

    name: str
    run_func: Callable
    aliases: list[str] | None = None
    help_text: str = ""

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []


class CommandTool(Tool):
    """Simple tool wrapper for commands with run functions."""

    def __init__(self, command: Command, parent: Traceable | None = None):
        config = ToolConfig(
            name=command.name,
            aliases=command.aliases or [],  # __post_init__ ensures this is never None
            help_text=command.help_text,
        )
        super().__init__(parent, config)
        self._run_func = command.run_func

    def run(self, **kwargs: Any) -> int:
        """Run the command function."""
        try:
            result = self._run_func(**kwargs)
            # If the function returns an int, use it as exit code
            if isinstance(result, int):
                return result
            # Otherwise, assume success
            return 0
        except Exception as e:
            if self.lg:
                self.lg.error(f"command '{self.name}' failed", extra={"exception": e})
            else:
                # Fallback to root logger if tool logger not available
                import logging

                logging.error(f"command '{self.name}' failed", extra={"exception": e})
            return 1


@dataclass
class ServerConfig:
    """Configuration for server components."""

    port: int = 8080
    host: str = "localhost"
    ssl_enabled: bool = False
    cors_origins: list[str] | None = None
    timeout: int = 30

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            self.cors_origins = []


@dataclass
class LoggingConfig:
    """Configuration for logging.

    Fields with None defaults will not override config file values during merge.
    Only explicitly set values will take precedence over config files.
    """

    level: str | None = None
    location: int | None = None
    micros: bool | None = None
    format_string: str | None = None
    location_color: str | None = None


@dataclass
class HotReloadConfig:
    """Configuration for hot-reload of logging settings.

    When enabled, changes to the config file are automatically detected
    and applied to all existing loggers without restart.
    """

    enabled: bool = False
    config_path: str | None = None
    section: str = "logging"
    debounce_ms: int = 500


class AppBuilder:
    """
    Fluent builder for constructing CLI applications.

    Provides a declarative API for building applications with tools,
    middleware, configuration, and lifecycle management.
    """

    # Default standard args configuration
    _DEFAULT_STANDARD_ARGS: dict[str, bool] = {
        "etc_dir": True,
        "log_level": True,
        "log_location": True,
        "log_micros": True,
        "log_topic": True,
        "quiet": True,
    }

    def __init__(self, name: str | None = None):
        """Initialize the application builder."""
        self._name: str | None = name
        self._config: Config | DotDict | None = None
        self._config_path: str | None = None  # Track config file path for hot-reload
        self._server_config: ServerConfig | None = None
        self._logging_config: LoggingConfig | None = None
        self._hot_reload_config: HotReloadConfig | None = None
        self._tools: list[Tool] = []
        self._commands: list[Command] = []
        self._middleware: list[Middleware] = []
        self._validation_rules: list[ValidationRule] = []
        self._hooks: HookManager = HookManager()
        self._plugins: PluginManager = PluginManager()
        self._custom_args: list[tuple] = []
        self._description: str | None = None
        self._version: str | None = None
        self._main_cls: type | None = None
        self._auto_load_config: bool = True  # Auto-load from --etc-dir by default
        self._standard_args: dict[str, bool] = self._DEFAULT_STANDARD_ARGS.copy()
        self._decorators: DecoratorAPI = DecoratorAPI(self)

    def with_name(self, name: str) -> "AppBuilder":
        """Set the application name."""
        self._name = name
        return self

    def with_description(self, description: str) -> "AppBuilder":
        """Set the application description."""
        self._description = description
        return self

    def with_version(self, version: str) -> "AppBuilder":
        """Set the application version."""
        self._version = version
        return self

    def config(self, path: str) -> "AppBuilder":
        """
        Load configuration from a YAML file.

        This method loads configuration and tracks the file path for hot-reload support.

        Args:
            path: Path to configuration YAML file

        Returns:
            Self for method chaining

        Example:
            app = (AppBuilder("myapp")
                .config("etc/app.yaml")
                .logging
                    .with_hot_reload(True)  # Can now use default path
                    .done()
                .build())
        """
        self._config = Config(path)
        self._config_path = path
        return self

    def with_config(self, config: Config | DotDict) -> "AppBuilder":
        """Set the application configuration."""
        self._config = config
        # Track path if Config has it
        if hasattr(config, "_config_path"):
            self._config_path = config._config_path
        return self

    def with_config_builder(self, builder: ConfigBuilder) -> "AppBuilder":
        """Set configuration using a config builder."""
        self._config = builder.build()
        return self

    def with_main_cls(self, cls: type) -> "AppBuilder":
        """Set the main application class."""
        self._main_cls = cls
        return self

    def without_auto_config(self) -> "AppBuilder":
        """
        Disable automatic configuration loading from --etc-dir.

        By default, the application framework will automatically attempt to load
        configuration from the directory specified by --etc-dir (or auto-detected
        etc directory) during App.setup(). Use this method to disable this behavior
        if you want full manual control over configuration loading.

        Returns:
            AppBuilder: Self for method chaining

        Example:
            app = (AppBuilder("myapp")
                .without_auto_config()  # Disable automatic config loading
                .build())
        """
        self._auto_load_config = False
        return self

    def _validate_standard_arg_name(self, name: str) -> None:
        """Validate that argument name is a valid standard arg."""
        valid_args = {
            "etc_dir",
            "log_level",
            "log_location",
            "log_micros",
            "log_topic",
            "quiet",
        }
        if name not in valid_args:
            raise ValueError(
                f"Invalid standard argument name: '{name}'. "
                f"Valid names are: {', '.join(sorted(valid_args))}"
            )

    def with_standard_args(self, **kwargs: bool) -> "AppBuilder":
        """
        Control which standard CLI arguments are enabled.

        When called without arguments, enables all standard arguments.
        When called with keyword arguments, sets specific arguments to True/False.

        Args:
            **kwargs: Keyword arguments matching standard arg names (etc_dir, log_level,
                      log_location, log_micros, quiet) with boolean values.

        Returns:
            AppBuilder: Self for method chaining

        Raises:
            ValueError: If invalid argument name or non-boolean value provided

        Examples:
            # Enable all standard args (explicit)
            AppBuilder("myapp").with_standard_args().build()

            # Disable specific args
            AppBuilder("myapp").with_standard_args(log_location=False, log_micros=False).build()

            # After disabling all, enable specific args
            AppBuilder("myapp").without_standard_args().with_standard_args(etc_dir=True).build()
        """
        if not kwargs:
            # No arguments: enable all
            for key in self._standard_args:
                self._standard_args[key] = True
        else:
            # Validate and apply specific settings
            for name, enabled in kwargs.items():
                self._validate_standard_arg_name(name)
                if not isinstance(enabled, bool):
                    raise ValueError(
                        f"Value for '{name}' must be a boolean, got {type(enabled).__name__}"
                    )
                self._standard_args[name] = enabled

        return self

    def without_standard_args(self) -> "AppBuilder":
        """
        Disable all standard CLI arguments.

        By default, the application framework adds standard arguments like --etc-dir,
        --log-level, --log-location, --log-micros, and -q/--quiet. Use this method
        to disable all of them if you want full manual control.

        You can selectively re-enable specific arguments using with_standard_args():
            AppBuilder("myapp")
                .without_standard_args()
                .with_standard_args(etc_dir=True, log_level=True)
                .build()

        Returns:
            AppBuilder: Self for method chaining

        Example:
            app = AppBuilder("myapp").without_standard_args().build()
        """
        for key in self._standard_args:
            self._standard_args[key] = False
        return self

    def tool(self, *args: Any, **kwargs: Any) -> Callable:
        """
        Decorator to register a tool from a function.

        Provides a decorator-based API for creating tools with less boilerplate.
        The decorated function receives `self` as the first parameter, which is
        the generated Tool instance with full framework access (lg, config, args).

        Example:
            builder = AppBuilder()

            @builder.tool(name="analyze", help="Analyze data")
            @builder.argument('--file', required=True)
            def analyze(self):
                self.lg.info(f"Analyzing {self.args.file}")
                return 0

            app = builder.build()

        Args:
            *args: Positional arguments passed to DecoratorAPI.tool()
            **kwargs: Keyword arguments passed to DecoratorAPI.tool()

        Returns:
            Decorator function
        """
        return self._decorators.tool(*args, **kwargs)

    @property
    def argument(self) -> Callable:
        """
        Decorator to add command-line arguments to a tool.

        Returns the argument decorator from DecoratorAPI.

        Example:
            @builder.tool()
            @builder.argument('--file', required=True)
            @builder.argument('--verbose', action='store_true')
            def process(self):
                self.lg.info(f"Processing {self.args.file}")

        Returns:
            Argument decorator function
        """
        return self._decorators.argument

    def build(self) -> App:
        """Build the application with all configured components."""
        config = self._merge_logging_into_config()
        app = _create_base_app(self._main_cls, config)
        _initialize_foundation(app, self)
        _register_components(app, self)
        _configure_external_services(app, self)
        return app

    def _merge_logging_into_config(self) -> Config | DotDict | None:
        """Merge logging config into base config, skipping None values."""
        if self._logging_config is None:
            return self._config

        from dataclasses import asdict

        from appinfra.dot_dict import DotDict

        # Get non-None logging values
        logging_dict = {
            k: v for k, v in asdict(self._logging_config).items() if v is not None
        }

        if not logging_dict:
            return self._config

        # Merge into config
        if self._config is None:
            return DotDict(logging=DotDict(**logging_dict))

        # Ensure logging section exists
        if not hasattr(self._config, "logging"):
            self._config.logging = DotDict()  # type: ignore[attr-defined]

        # Update logging section with non-None values
        for key, value in logging_dict.items():
            setattr(self._config.logging, key, value)  # type: ignore[attr-defined]

        return self._config

    def create_config_builder(self) -> ConfigBuilder:
        """Create a new configuration builder."""
        return ConfigBuilder()

    def create_server_config_builder(self) -> ServerConfigBuilder:
        """Create a new server configuration builder."""
        return ServerConfigBuilder()

    def create_logging_config_builder(self) -> LoggingConfigBuilder:
        """Create a new logging configuration builder."""
        return LoggingConfigBuilder()

    def create_tool_builder(self, name: str) -> ToolBuilder:
        """Create a new tool builder."""
        return ToolBuilder(name)

    def create_middleware_builder(self, name: str) -> MiddlewareBuilder:
        """Create a new middleware builder."""
        return MiddlewareBuilder(name)

    def create_validation_builder(self) -> ValidationBuilder:
        """Create a new validation builder."""
        return ValidationBuilder()

    def create_hook_builder(self) -> HookBuilder:
        """Create a new hook builder."""
        return HookBuilder()

    # ========================================================================
    # Focused Configurers (New API - Recommended)
    # ========================================================================

    @property
    def tools(self) -> ToolConfigurer:
        """
        Access tool configuration builder.

        Returns a focused builder for configuring tools, commands, and plugins.
        Use .done() to return to the main AppBuilder.

        Example:
            app = (AppBuilder("myapp")
                .tools
                    .with_tool(MyTool())
                    .with_plugin(DatabasePlugin())
                    .done()
                .build())

        Returns:
            ToolConfigurer instance for method chaining
        """
        return ToolConfigurer(self)

    @property
    def server(self) -> ServerConfigurer:
        """
        Access server configuration builder.

        Returns a focused builder for configuring server and middleware.
        Use .done() to return to the main AppBuilder.

        Example:
            app = (AppBuilder("myapp")
                .server
                    .with_port(8080)
                    .with_middleware(AuthMiddleware())
                    .done()
                .build())

        Returns:
            ServerConfigurer instance for method chaining
        """
        return ServerConfigurer(self)

    @property
    def logging(self) -> LoggingConfigurer:
        """
        Access logging configuration builder.

        Returns a focused builder for configuring logging.
        Use .done() to return to the main AppBuilder.

        Example:
            app = (AppBuilder("myapp")
                .logging
                    .with_level("debug")
                    .with_micros(True)
                    .done()
                .build())

        Returns:
            LoggingConfigurer instance for method chaining
        """
        return LoggingConfigurer(self)

    @property
    def advanced(self) -> AdvancedConfigurer:
        """
        Access advanced configuration builder.

        Returns a focused builder for hooks, validation, and custom arguments.
        Use .done() to return to the main AppBuilder.

        Example:
            app = (AppBuilder("myapp")
                .advanced
                    .with_hook("startup", on_startup)
                    .with_validation_rule(rule)
                    .done()
                .build())

        Returns:
            AdvancedConfigurer instance for method chaining
        """
        return AdvancedConfigurer(self)


def create_app_builder(name: str) -> AppBuilder:
    """
    Create a new application builder.

    Args:
        name: Name of the application

    Returns:
        AppBuilder instance

    Example:
        app = create_app_builder("myapp").with_help("My app").build()
    """
    return AppBuilder(name)
