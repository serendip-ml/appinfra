# Example Plugins

`example_plugins.py` shows what a plugin can contribute to an app from its `configure(builder)`
hook, and builds an app from four of them.

```bash
python example_plugins.py --help     # tools contributed by the plugins
python example_plugins.py metrics    # run one of them
```

## What a plugin can contribute

| Block               | Example                                                            |
|---------------------|--------------------------------------------------------------------|
| `builder.tools`     | `with_tool_builder(ToolBuilder("migrate")...)`                     |
| `builder.lifecycle` | `with_hook_builder(HookBuilder().on_startup(...).on_shutdown(...))` |

Inside `configure()` a block is closed with `done()` like anywhere else; a plugin that leaves one
open fails at `build()` with the plugin name and the line that opened it.

## The plugins

- **DatabasePlugin** - `migrate` and `db-status` tools; connect/disconnect lifecycle hooks.
- **AuthPlugin** - `login` and `logout` tools.
- **LoggingPlugin** - `log-level` tool; startup and error hooks.
- **MetricsPlugin** - `metrics` tool reporting the counts it collects.

## Building the app

```python
app = (
    AppBuilder("plugins-demo")
    .cli(log_level=True)
    .tools(
        plugins=[
            DatabasePlugin(),
            AuthPlugin(auth_type="jwt"),
            LoggingPlugin(),
            MetricsPlugin(),
        ]
    )
    .build()
)
```

## Writing a plugin

```python
from appinfra.app.builder.plugin import Plugin
from appinfra.app.builder.tool import ToolBuilder


class MyPlugin(Plugin):
    def __init__(self):
        super().__init__("my-plugin")

    def configure(self, builder):
        builder.tools.with_tool_builder(
            ToolBuilder("my-command")
            .with_help("My custom command")
            .with_run_function(self._run)
        ).done()

    def _run(self, tool, **kwargs):
        tool.lg.info("Running my custom command")
        return 0
```

`initialize(application)` runs after the `App` is built and `cleanup(application)` at shutdown;
both are optional.
