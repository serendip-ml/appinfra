# AppBuilder - Fluent API

Fluent builder for constructing CLI applications with tools, logging, and lifecycle management.

## AppBuilder

```python
class AppBuilder:
    def __init__(self, name: str | None = None): ...
```

**Chain Methods:**
- `with_name(name)` - Set application name
- `with_description(desc)` - Set description
- `with_version(version)` - Set version string
- `with_config(config)` - Set Config or DotDict configuration
- `config(path)` - Load config from file path (tracks path for hot-reload)
- `with_main_cls(cls)` - Use custom App subclass
- `without_auto_config()` - Disable automatic config loading
- `with_standard_args(**kwargs)` - Enable/disable standard CLI args
- `without_standard_args()` - Disable all standard args
- `build()` - Build and return the App instance

**Sub-builders (accessed via properties):**
- `.tools` - ToolConfigurer for adding tools
- `.logging` - LoggingConfigurer for log settings
- `.server` - ServerConfigurer for HTTP server
- `.advanced` - AdvancedConfigurer for hooks, middleware, custom args

## ToolConfigurer

Accessed via `AppBuilder().tools`:

```python
app = (
    AppBuilder("myapp")
    .tools
        .with_tool(MyTool())      # Add a Tool instance
        .with_plugin(MyPlugin())  # Add a Plugin
        .done()                   # Return to AppBuilder
    .build()
)
```

## LoggingConfigurer

Accessed via `AppBuilder().logging()`:

```python
app = (
    AppBuilder("myapp")
    .logging()
        .with_level("info")       # Set log level
        .with_location(1)         # Show file/line (0=none, 1=file:line, 2=full path)
        .with_micros(True)        # Microsecond timestamps
        .with_colors(True)        # Enable colored output
        .with_format("%(msg)s")   # Custom format string
        .with_hot_reload(True)    # Enable config hot-reload (requires watchdog)
        .done()
    .build()
)
```

## ServerConfigurer

Accessed via `AppBuilder().server`:

```python
app = (
    AppBuilder("myapp")
    .server
        .with_port(8080)
        .with_host("0.0.0.0")
        .done()
    .build()
)
```

## AdvancedConfigurer

Accessed via `AppBuilder().advanced`:

```python
def on_startup(ctx):
    ctx.app.lg.info("Starting...")

app = (
    AppBuilder("myapp")
    .advanced
        .with_hook("startup", on_startup)
        .with_argument("-v", "--verbose", action="store_true")
        .done()
    .build()
)
```

## Complete Example

```python
from appinfra.app.builder import AppBuilder
from appinfra.app.tools import Tool, ToolConfig

class GreetTool(Tool):
    def __init__(self, parent=None):
        super().__init__(parent, ToolConfig(
            name="greet",
            aliases=["g"],
            help_text="Greet someone"
        ))

    def add_args(self, parser):
        parser.add_argument("--name", required=True, help="Name to greet")

    def run(self, **kwargs):
        self.lg.info(f"Hello, {self.args.name}!")
        return 0

app = (
    AppBuilder("myapp")
    .with_description("My CLI application")
    .with_version("1.0.0")
    .logging
        .with_level("info")
        .with_location(1)
        .done()
    .tools
        .with_tool(GreetTool())
        .done()
    .build()
)

if __name__ == "__main__":
    exit(app.main())
```

## Standard Arguments

By default, AppBuilder adds these CLI arguments:

| Argument | Description |
|----------|-------------|
| `--etc-dir` | Configuration directory path |
| `--log-level` | Log level (trace2, trace, debug, info, warning, error) |
| `--log-location` | Show file location in logs (0, 1, 2) |
| `--log-micros` | Use microsecond timestamps |
| `--log-topic` | Log topic filter |
| `-q, --quiet` | Suppress output |

Disable with `.without_standard_args()` or selectively with `.with_standard_args(log_micros=False)`.

## Hot-Reload Logging

Enable automatic config reloading when config files change (requires `pip install
appinfra[hotreload]`):

```python
app = (
    AppBuilder("my-service")
    .config("etc/config.yaml")  # Track config path
    .logging()
        .with_hot_reload(True)  # Enable watching
        .done()
    .build()
)
```

Or with explicit config path:

```python
app = (
    AppBuilder("my-service")
    .logging()
        .with_hot_reload(
            enabled=True,
            config_path="etc/logging.yaml",
            section="logging",
            debounce_ms=500
        )
        .done()
    .build()
)
```

See [Hot-Reload Logging Guide](../guides/hot-reload-logging.md) for full documentation.

## See Also

- [Application Framework](app.md) - Tool and ToolConfig
- [Logging System](logging.md) - LoggingBuilder
- [Hot-Reload Logging](../guides/hot-reload-logging.md) - Dynamic config reloading
