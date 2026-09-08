# AppBuilder - Fluent API

Faceted builder for CLI applications: one block per axis, each closed with `done()` or called
with keywords, which returns the `AppBuilder` directly. Mixing both spellings in one chain is the
norm. One block is open at a time: opening another block, or calling `build()`, while a block is
open raises `ValueError` naming the block and the line that opened it. Plugins that touch a block
inside `configure()` close it the same way.

## AppBuilder

```python
class AppBuilder:
    def __init__(self, name: str | None = None): ...
```

**Top level (identity only):**
- `AppBuilder(name)` - Application name
- `with_description(desc)` - Set description
- `with_main_cls(cls)` - Use a custom `App` subclass
- `build()` - Build and return the `App` instance

**Blocks (accessed via properties):**

| Block        | Holds                                                    | Backed by        |
|--------------|----------------------------------------------------------|------------------|
| `.config`    | config source: spec, programmatic overrides, hot reload  | app-only         |
| `.cli`       | standard flags, flag presentation, custom arguments      | app-only         |
| `.logging`   | display options, topic levels, handlers, extra fields    | `LoggingBuilder` |
| `.tools`     | tools, commands, plugins, main tool                      | app-only         |
| `.lifecycle` | hooks by event                                           | app-only         |
| `.version`   | semver, build info, tracked packages                     | app-only         |

`.logging` is the standalone builder bound to the app: every method of
[`LoggingBuilder`](logging.md) is available on the block, and `build()` on the block raises,
since the app builds the logger itself.

Two spellings per block write the same state:

```python
# chained: block methods, then done()
AppBuilder("myapp").cli.with_flags(etc_dir=True, log=True).done()

# keyword: call the block, get the AppBuilder back
AppBuilder("myapp").cli(etc_dir=True, log=True)
```

The keyword form takes scalar fields by keyword and homogeneous items by position, as in
`.tools(A(), B())`. Anything structured, such as argparse arguments, handlers, routes, or hooks
from a `HookBuilder`, is chained only.

## Complete Example

```python
from appinfra.app.builder import AppBuilder
from appinfra.app.tools import Tool, ToolConfig


class GreetTool(Tool):
    def __init__(self, parent=None):
        super().__init__(
            parent, ToolConfig(name="greet", aliases=["g"], help_text="Greet someone")
        )

    def add_args(self, parser):
        parser.add_argument("--name", required=True, help="Name to greet")

    def run(self, **kwargs):
        self.lg.info(f"Hello, {self.args.name}!")
        return 0


app = (
    AppBuilder("myapp")
    .with_description("My CLI application")
    .config.with_spec("myorg", "myapp")
    .done()
    .cli(etc_dir=True, config_file=True, log=True, version=True)
    .logging(level="info", location=1)
    .tools.with_tool(GreetTool())
    .done()
    .version(semver="1.0.0")
    .build()
)

if __name__ == "__main__":
    exit(app.main())
```

## config block

Declare the config source with the `config` block. The App resolves it at setup under the
[config protocol](../guides/config-protocol.md): `--config`, `--etc-dir`, a project-local
`etc/`, XDG overlays, then the packaged base.

```python
# Base: etc/inference.yaml beside the `inference` module, or beside the calling script
app = AppBuilder("inference").config.with_spec("myorg", "inference").done().build()

# Base that deviates from the etc/<name>.yaml layout
app = (
    AppBuilder("myapp")
    .config.with_spec("myorg", "myapp", filename="infra.yaml")
    .done()
    .build()
)
```

Programmatic config via builder methods takes precedence over the loaded file. A resolved file
that does not exist raises `FileNotFoundError` at setup.

With `.cli(etc_dir=True)`, the `--etc-dir` CLI argument redirects the load:
```bash
./cli.py --etc-dir /custom/path serve
# → loads /custom/path/inference.yaml
```

Without a spec, no file is loaded; config comes from `.config.with_overrides()` and CLI args:
```python
app = (
    AppBuilder("myapp")
    .config.with_overrides({"logging": {"level": "info"}})
    .done()
    .build()
)
```

See [AppBuilder.config](config.md#appbuilderconfig) for the full block.

## cli block

Standard flags are **off by default** except `-h/--help`. Flags merge onto the current set.

```python
# Named flags
AppBuilder("myapp").cli(etc_dir=True, log_level=True, quiet=True).build()

# Every logging flag at once
AppBuilder("myapp").cli(log=True).build()

# Every standard flag
AppBuilder("myapp").cli.with_all_flags().done().build()

# Every standard flag except one
AppBuilder("myapp").cli.with_all_flags().without_flag("log_json").done().build()

# Locked down: clear everything (help included), then name what stays
AppBuilder("myapp").cli.without_flags().with_flags(etc_dir=True).done().build()
```

**Available flags:**

| Flag           | CLI Flag           | Description                                              |
|----------------|--------------------|----------------------------------------------------------|
| `help`         | `-h, --help`       | Show help message (default: True)                        |
| `config_file`  | `-c, --config`     | Config file path or name                                 |
| `etc_dir`      | `--etc-dir`        | Configuration directory path                             |
| `log_level`    | `-l, --log-level`  | Log level (trace2, trace, debug, info, warning, error)   |
| `log_json`     | `--log-json`       | Output logs in JSON format                               |
| `log_location` | `--log-location`   | Show file location in logs (0, 1, 2)                     |
| `log_micros`   | `--log-micros`     | Use microsecond timestamps                               |
| `log_topic`    | `--log-topic`      | Log topic filter                                         |
| `log_colors`   | `--no-log-colors`  | Disable colored log output                               |
| `quiet`        | `-q, --quiet`      | Suppress output                                          |
| `version`      | `-v, --version`    | Print the version declared on the `.version` block       |

**Alias:** `log=True` enables the seven log-related flags (`log_level`, `log_location`,
`log_micros`, `log_topic`, `log_colors`, `log_json`, `quiet`). An explicit key wins over the
alias.

**Bulk on/off:** `with_all_flags()` enables every standard flag (`help` included);
`without_flags()` clears everything. `without_flag(name)` disables one flag (singular of
`without_flags()`); the `log` alias is rejected — use `with_flags(log=False)` for bulk
disable.

**One flag with its presentation:** `with_flag(name, **argparse_kwargs)` enables one standard
flag and overrides its argparse presentation (`help`, `metavar`, `choices`, `type`, `nargs`,
`action`). Overrides merge on top of framework values; only the passed keys change.

```python
AppBuilder("myapp").cli.with_flag(
    "log_level", help="verbosity of the service log"
).done().build()
```

Restrictions:
- `default` is rejected: a default is a value, and values come from the subsystem block
  (`.logging.with_level(...)`) or the config file, never from the flag.
- `dest` is rejected: the framework reads parsed args by a fixed attribute name set internally,
  which may differ from the flag name (`log_topic` is read as `args.log_topics`).
- `log` (an alias) and `help` (argparse's `add_help`) have no single action to present.

> The framework populates `app.etc_dir` when `etc_dir` is enabled; read it from inside
> `Tool.configure()`. With a spec it is the resolved file's directory. See
> [config docs](config.md#reading-appetc_dir) for the full resolution table.

> Overriding shape-changing kwargs (`action`, `nargs`, `required`) is allowed but the consumer
> takes on the responsibility of keeping framework assumptions intact. For example, flipping
> `--no-log-colors` from `store_false` to `store_true` inverts the flag's user-visible meaning;
> setting `required=True` on `--etc-dir` makes argparse reject runs that rely on the spec's own
> resolution.

**Custom arguments:** `with_argument(*args, **kwargs)` takes the arguments of
`parser.add_argument` and is chained only.

```python
AppBuilder("myapp").cli.with_argument("--dry-run", action="store_true").done()
```

**Precedence:** CLI args override environment variables, which override YAML config values.
See [Configuration Precedence](../guides/configuration-precedence.md) for the full precedence
rules.

### `-c/--config`

The `-c/--config` argument selects the config file at runtime for an app with a spec:

```bash
# Direct path (absolute, or ./, ../, ~/ prefix)
myapp -c /etc/myapp/prod.yaml
myapp -c ./local-config.yaml

# Bare filename: under --etc-dir when given, otherwise the current directory
myapp -c custom.yaml                    # loads ./custom.yaml
myapp --etc-dir /app/etc -c prod.yaml   # loads /app/etc/prod.yaml
```

Enable via `.cli(etc_dir=True, config_file=True)`:

```python
app = (
    AppBuilder("myapp")
    .config.with_spec("myorg", "myapp")
    .done()
    .cli(etc_dir=True, config_file=True)
    .build()
)
```

## logging block

`LoggingScope` is [`LoggingBuilder`](logging.md) bound to the app. Options set here go into the
programmatic config layer, above the config file and below CLI flags; an option left untouched
keeps the file's value.

```python
app = (
    AppBuilder("myapp")
    .logging.with_level("info")
    .with_location(1)  # Show file/line (0=none, 1=file:line, 2=full path)
    .with_micros()  # Microsecond timestamps
    .with_topic_level("/infra/db/*", "debug")
    .with_file_handler("app.log")
    .with_extra(service="api")
    .done()
    .build()
)

app = AppBuilder("myapp").logging(level="info", location=1).build()
```

Keyword fields: `level`, `location`, `micros`, `colors`, `location_color`, `topic_levels`,
`runtime_updates`. Handlers and `with_extra` are chained only; handlers become
`logging.handlers` entries and extra fields become `logging.extra`, so the app's root logger gets
both. Handlers from the block are keyed `builder_0`, `builder_1` and so on, so they never merge
into a handler the config file names. A handler with no config form, a database handler or a
console handler on a stream other than stdout/stderr, fails at `done()`; add such a handler to
the root logger from a startup hook instead. `with_runtime_updates()` is the one scope-only
method; everything else is the standalone builder's.

## tools block

```python
app = (
    AppBuilder("myapp")
    .tools.with_tool(MyTool())  # Add a Tool instance
    .with_plugin(MyPlugin())  # Add a Plugin
    .with_main("run")  # Tool that runs without a subcommand
    .done()
    .build()
)

app = (
    AppBuilder("myapp")
    .tools(MyTool(), OtherTool(), plugins=[MyPlugin()], main="run")
    .build()
)
```

`with_cmd(name, run_func, aliases=..., help_text=...)` and `with_tool_builder(builder)` are
chained only.

### Main Tool (Single-Tool Apps)

For single-purpose apps, `with_main()` runs a tool without requiring a subcommand:

```python
app = AppBuilder("proxy").tools(main="run").build()


@app.tool(name="run")
def run_proxy(self):
    self.lg.info("Starting proxy...")
    return 0
```

Now the app can be invoked without the subcommand:
```bash
# Before: ./proxy.py run --port 8080
# After:  ./proxy.py --port 8080
```

Accepts either a tool name or a `Tool` instance; an instance is registered as well:
```python
AppBuilder("proxy").tools.with_main("run").done()  # by name
AppBuilder("proxy").tools.with_main(my_tool).done()  # by instance
```

## lifecycle block

```python
def on_startup(ctx):
    ctx.application.lg.info("Starting...")


app = AppBuilder("myapp").lifecycle.with_hook("startup", on_startup).done().build()

app = AppBuilder("myapp").lifecycle(startup=on_startup, shutdown=on_shutdown).build()
```

`with_hook(event, callback, priority=0)` registers one callback; higher priority runs first.
`with_hook_builder(HookBuilder)` registers every hook of a builder, keeping priority, `once` and
conditions. The standard events are `startup`, `shutdown`, `tool_start`, `tool_end`, `error`,
`before_parse`, `after_parse`, `before_setup` and `after_setup`; the keyword form accepts only
those, so a misspelled name fails at the call. Custom event names go through `with_hook`.

## version block

```python
app = (
    AppBuilder("myapp")
    .version.with_semver("1.0.0")
    .with_build_info()  # Commit hash from _build_info.py
    .with_package("mylib")  # Track a dependency's version and commit
    .done()
    .build()
)

app = (
    AppBuilder("myapp")
    .version(semver="1.0.0", build_info=True, package="mylib")
    .build()
)
```

Exposing `-v/--version` is the `.cli` block's `version` flag; it prints this block's text and
requires a semver. Build info and tracked packages are logged at startup unless
`startup_log=False` (`without_startup_log()` chained).

## Hot-Reload Logging

Enable automatic config reloading when config files change (requires `pip install
appinfra[hotreload]`):

```python
app = (
    AppBuilder("my-service")
    .config.with_spec("myorg", "my-service")
    .with_hot_reload(True)  # Watch the resolved config file
    .done()
    .build()
)
```

See [Hot-Reload Logging Guide](../guides/hot-reload-logging.md) for full documentation.

## See Also

- [Decorator API with Config Files](../guides/decorator-config-pattern.md) - Build app, then decorate
- [Application Framework](app.md) - Tool and ToolConfig
- [Logging System](logging.md) - LoggingBuilder, the standalone builder behind `.logging`
- [FastAPI Server](fastapi.md) - ServerBuilder, for a tool that serves HTTP
- [Hot-Reload Logging](../guides/hot-reload-logging.md) - Dynamic config reloading
