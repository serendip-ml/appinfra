# Example Plugins

`example_plugins.py` shows what a plugin can contribute to an app from its `configure(builder)`
hook, and builds an app from four of them.

```bash
python example_plugins.py --help     # tools contributed by the plugins
python example_plugins.py metrics    # run one of them
python example_plugins.py serve      # HTTP server with the plugins' routes and middleware
```

## What a plugin can contribute

| Block               | Example                                                            |
|---------------------|--------------------------------------------------------------------|
| `builder.tools`     | `with_tool_builder(ToolBuilder("migrate")...)`                     |
| `builder.lifecycle` | `with_hook_builder(HookBuilder().on_startup(...).on_shutdown(...))` |
| `builder.server`    | `routes.with_route("/metrics", handler)`, `routes.with_middleware(cls, **options)` |

Routes and middleware go on the app's HTTP server, so the app must declare `.server`; the
server is built after every plugin has configured it, and `serve` starts it. A plugin that
configures `.server` on an app without one fails at `build()`.

## The plugins

- **DatabasePlugin** - `migrate` and `db-status` tools; connect/disconnect lifecycle hooks.
- **AuthPlugin** - `login` and `logout` tools; `BearerAuthMiddleware`, which rejects `/api/*`
  requests without an `Authorization` header.
- **LoggingPlugin** - `log-level` tool; startup and error hooks.
- **MetricsPlugin** - `metrics` tool; a `/metrics` route; `RequestCounterMiddleware`, which counts
  requests per path into the dict the route serves.

The middleware classes are plain ASGI callables, no framework base class: the server adds them
with `add_middleware(cls, **options)`, which instantiates `cls(app, **options)`.

## Building the app

```python
app = (
    AppBuilder("plugins-demo")
    .cli(log_level=True)
    .server(port=8090, title="Plugins demo")
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
        )

    def _run(self, tool, **kwargs):
        tool.lg.info("Running my custom command")
        return 0
```

`initialize(application)` runs after the `App` is built and `cleanup(application)` at shutdown;
both are optional.
