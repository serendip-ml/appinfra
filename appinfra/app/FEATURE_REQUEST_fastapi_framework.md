# Feature Request: FastAPI Server Framework for appinfra

**Requested by:** inference team
**Target module:** `appinfra/app/fastapi/`
**Priority:** High (blocking new project)

---

## Summary

Add a production-ready FastAPI + Uvicorn server framework to appinfra that supports subprocess
isolation with queue-based IPC. This enables building HTTP APIs where the web server runs in a
separate process from the main application logic, communicating via multiprocessing queues.

---

## Motivation

### Problem

We're building multiple services that need:
1. FastAPI-based HTTP APIs
2. Subprocess isolation (API server in child process, business logic in main process)
3. Queue-based IPC between processes
4. Consistent patterns across services

Currently, we've implemented this pattern manually in the inference server
(`inference/serving/api/`). With a second project needing the same architecture, we want to
extract this into a reusable framework.

### Why Subprocess Isolation?

- **Resource isolation:** Heavy computation (ML inference, data processing) stays in main process
- **Crash isolation:** API server crashes don't kill the engine; can be restarted
- **Logging isolation:** Separate log streams for API vs engine
- **Process management:** Clean shutdown, health monitoring, restart capabilities

### Why appinfra?

- Follows existing `appinfra.app` patterns (fluent builders, lifecycle, plugins)
- Can integrate with `AppBuilder` for CLI apps that also serve HTTP
- Centralizes web serving infrastructure alongside CLI infrastructure
- Lower-level than `ware` (which is for domain abstractions like LLM APIs)

---

## Proposed Solution

### Module Location

```
appinfra/app/fastapi/
```

Lives under `app/` because FastAPI servers are a type of application, alongside the CLI framework.

### Module Structure

```
appinfra/app/fastapi/
    __init__.py                 # Public API exports
    builder/
        __init__.py
        server.py               # ServerBuilder (main fluent API)
        route.py                # RouteConfigurer
        subprocess.py           # SubprocessConfigurer
        uvicorn.py              # UvicornConfigurer
    config/
        __init__.py
        api.py                  # ApiConfig dataclass
        uvicorn.py              # UvicornConfig dataclass
        ipc.py                  # IPCConfig dataclass
    runtime/
        __init__.py
        server.py               # Server (runtime instance)
        subprocess.py           # SubprocessManager
        ipc.py                  # IPCChannel (queue abstraction)
        adapter.py              # FastAPIAdapter (wraps FastAPI construction)
        logging.py              # Subprocess logging isolation
    plugin.py                   # ServerPlugin for AppBuilder integration
```

### Public API

```python
from appinfra.app.fastapi import (
    # Builder
    ServerBuilder,

    # Runtime
    Server,
    IPCChannel,

    # Config
    ApiConfig,
    UvicornConfig,
    IPCConfig,

    # AppBuilder integration
    ServerPlugin,
)
```

---

## Technical Specification

### 1. Configuration Dataclasses

#### UvicornConfig

```python
@dataclass
class UvicornConfig:
    """Uvicorn server configuration."""
    workers: int = 1
    timeout_keep_alive: int = 5
    limit_concurrency: int | None = None
    limit_max_requests: int | None = None
    backlog: int = 2048
    log_level: str = "warning"
    access_log: bool = False
    ssl_keyfile: str | None = None
    ssl_certfile: str | None = None
```

#### ApiConfig

```python
@dataclass
class ApiConfig:
    """HTTP API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "API Server"
    description: str = ""
    version: str = "0.1.0"
    response_timeout: float = 60.0
    log_file: str | None = None  # For subprocess log isolation
    uvicorn: UvicornConfig = field(default_factory=UvicornConfig)
```

#### IPCConfig

```python
@dataclass
class IPCConfig:
    """Inter-process communication configuration."""
    poll_interval: float = 0.01      # Response queue polling interval
    queue_timeout: float = 0.01      # Queue.get() timeout
    max_pending: int = 100           # Max pending requests before rejection
```

---

### 2. Builder API

#### ServerBuilder (Main Entry Point)

```python
class ServerBuilder:
    """
    Fluent builder for FastAPI servers with optional subprocess isolation.

    Follows appinfra.app.AppBuilder patterns:
    - Method chaining with with_*() methods
    - Focused configurers accessed via properties (.routes, .subprocess, .uvicorn)
    - .done() returns to parent builder
    - .build() creates runtime instance
    """

    def __init__(self, name: str): ...

    # Direct configuration
    def with_host(self, host: str) -> "ServerBuilder": ...
    def with_port(self, port: int) -> "ServerBuilder": ...
    def with_title(self, title: str) -> "ServerBuilder": ...
    def with_description(self, description: str) -> "ServerBuilder": ...
    def with_version(self, version: str) -> "ServerBuilder": ...
    def with_timeout(self, timeout: float) -> "ServerBuilder": ...
    def with_config(self, config: ApiConfig) -> "ServerBuilder": ...

    # Focused configurers
    @property
    def routes(self) -> "RouteConfigurer": ...

    @property
    def subprocess(self) -> "SubprocessConfigurer": ...

    @property
    def uvicorn(self) -> "UvicornConfigurer": ...

    # Build
    def build(self) -> "Server": ...
```

#### RouteConfigurer

```python
class RouteConfigurer:
    """Focused builder for route and middleware configuration."""

    def __init__(self, parent: ServerBuilder): ...

    def with_route(
        self,
        path: str,
        handler: Callable,
        methods: list[str] | None = None,  # Default: ["GET"]
        response_model: type | None = None,
        tags: list[str] | None = None,
        **kwargs,  # Additional FastAPI route kwargs
    ) -> "RouteConfigurer": ...

    def with_router(
        self,
        router: APIRouter,
        prefix: str = "",
        tags: list[str] | None = None,
    ) -> "RouteConfigurer": ...

    def with_exception_handler(
        self,
        exc_class: type[Exception],
        handler: Callable,
    ) -> "RouteConfigurer": ...

    def with_middleware(
        self,
        middleware_class: type,
        **options,
    ) -> "RouteConfigurer": ...

    def with_cors(
        self,
        origins: list[str],
        allow_credentials: bool = False,
        allow_methods: list[str] | None = None,  # Default: ["*"]
        allow_headers: list[str] | None = None,  # Default: ["*"]
    ) -> "RouteConfigurer": ...

    def done(self) -> ServerBuilder: ...
```

#### SubprocessConfigurer

```python
class SubprocessConfigurer:
    """Focused builder for subprocess and IPC configuration."""

    def __init__(self, parent: ServerBuilder): ...

    def with_ipc(
        self,
        request_q: mp.Queue,
        response_q: mp.Queue,
    ) -> "SubprocessConfigurer":
        """Enable subprocess mode with queue-based IPC."""
        ...

    def with_log_file(self, path: str) -> "SubprocessConfigurer":
        """Isolate subprocess logs to file (redirects stdout/stderr too)."""
        ...

    def with_poll_interval(self, interval: float) -> "SubprocessConfigurer": ...
    def with_max_pending(self, max_pending: int) -> "SubprocessConfigurer": ...
    def with_config(self, config: IPCConfig) -> "SubprocessConfigurer": ...

    def done(self) -> ServerBuilder: ...
```

#### UvicornConfigurer

```python
class UvicornConfigurer:
    """Focused builder for Uvicorn configuration."""

    def __init__(self, parent: ServerBuilder): ...

    def with_workers(self, workers: int) -> "UvicornConfigurer": ...
    def with_timeout_keep_alive(self, timeout: int) -> "UvicornConfigurer": ...
    def with_limit_concurrency(self, limit: int) -> "UvicornConfigurer": ...
    def with_limit_max_requests(self, limit: int) -> "UvicornConfigurer": ...
    def with_backlog(self, backlog: int) -> "UvicornConfigurer": ...
    def with_log_level(self, level: str) -> "UvicornConfigurer": ...
    def with_access_log(self, enabled: bool = True) -> "UvicornConfigurer": ...
    def with_ssl(
        self,
        keyfile: str,
        certfile: str,
    ) -> "UvicornConfigurer": ...
    def with_config(self, config: UvicornConfig) -> "UvicornConfigurer": ...

    def done(self) -> ServerBuilder: ...
```

---

### 3. Runtime Components

#### Server

```python
class Server:
    """
    Runtime HTTP server instance.

    Supports two modes:
    1. Direct mode: uvicorn.run() in current process (blocking)
    2. Subprocess mode: uvicorn in child process with queue IPC (non-blocking)

    Mode is determined by whether .subprocess.with_ipc() was called during building.
    """

    def __init__(
        self,
        name: str,
        config: ApiConfig,
        app: FastAPI,
        subprocess_manager: SubprocessManager | None = None,
        ipc_channel: IPCChannel | None = None,
    ): ...

    # Lifecycle
    def start(self) -> None:
        """
        Start server (blocking).

        In direct mode: calls uvicorn.run() directly.
        In subprocess mode: starts subprocess and blocks on join().
        """
        ...

    def start_subprocess(self) -> mp.Process:
        """
        Start server in subprocess (non-blocking).

        Returns the Process object for monitoring.
        Only available in subprocess mode.

        Raises:
            RuntimeError: If not in subprocess mode
        """
        ...

    def stop(self, timeout: float = 5.0) -> None:
        """
        Gracefully stop the server.

        Uses terminate -> join(timeout) -> kill pattern.
        """
        ...

    # Properties
    @property
    def app(self) -> FastAPI:
        """Access underlying FastAPI application."""
        ...

    @property
    def ipc(self) -> IPCChannel | None:
        """Access IPC channel (None if direct mode)."""
        ...

    @property
    def is_running(self) -> bool: ...

    @property
    def is_subprocess_mode(self) -> bool: ...
```

#### SubprocessManager

```python
class SubprocessManager:
    """
    Manages uvicorn subprocess lifecycle.

    Handles:
    - Process spawning with proper argument passing
    - Log isolation setup in subprocess
    - Graceful shutdown with fallback kill
    - Process health monitoring
    """

    def __init__(
        self,
        target: Callable,
        args: tuple,
        log_file: str | None = None,
        shutdown_timeout: float = 5.0,
    ): ...

    def start(self) -> mp.Process: ...
    def stop(self) -> None: ...
    def is_alive(self) -> bool: ...

    @property
    def process(self) -> mp.Process | None: ...
    @property
    def pid(self) -> int | None: ...
```

#### IPCChannel

```python
class IPCChannel:
    """
    Bidirectional queue-based IPC for subprocess communication.

    Provides async interface for request/response pattern used in
    FastAPI route handlers to communicate with main process.

    Used inside the subprocess (FastAPI handlers) to:
    1. Submit requests to main process via request_q
    2. Wait for responses from main process via response_q
    3. Handle streaming responses (multiple chunks per request)
    """

    def __init__(
        self,
        request_q: mp.Queue,
        response_q: mp.Queue,
        config: IPCConfig,
    ): ...

    # Request/Response
    async def submit(
        self,
        request: Any,
        timeout: float | None = None,
    ) -> Any:
        """
        Submit request and wait for response.

        Args:
            request: Request object (must have .id attribute)
            timeout: Override default response timeout

        Returns:
            Response object from main process

        Raises:
            TimeoutError: If response not received within timeout
            asyncio.CancelledError: If polling task cancelled
        """
        ...

    async def submit_streaming(
        self,
        request: Any,
    ) -> AsyncIterator[Any]:
        """
        Submit streaming request and yield response chunks.

        Yields chunks until one with is_final=True is received.
        """
        ...

    # Lifecycle (called by Server)
    async def start_polling(self) -> None:
        """Start background task to poll response queue."""
        ...

    async def stop_polling(self) -> None:
        """Stop polling and cancel pending requests."""
        ...

    # Properties
    @property
    def pending_count(self) -> int:
        """Number of requests awaiting response."""
        ...
```

---

### 4. AppBuilder Integration

#### ServerPlugin

```python
class ServerPlugin(Plugin):
    """
    Plugin to integrate FastAPI server with AppBuilder CLI apps.

    Allows CLI applications to also serve HTTP by adding a "serve" tool
    that starts the configured server.

    Example:
        server = (ServerBuilder("myapi")
            .with_port(8000)
            .routes.with_route("/health", health).done()
            .build())

        app = (AppBuilder("myapp")
            .tools.with_plugin(ServerPlugin(server)).done()
            .build())

        # Now `myapp serve` starts the HTTP server
    """

    def __init__(
        self,
        server: Server,
        tool_name: str = "serve",
        tool_help: str = "Start the HTTP server",
    ): ...

    def configure(self, builder: AppBuilder) -> None:
        """Register serve tool with AppBuilder."""
        ...

    def initialize(self, app: App) -> None:
        """Called when app starts."""
        ...

    def cleanup(self, app: App) -> None:
        """Stop server on app shutdown."""
        ...
```

---

## Usage Examples

### Example 1: Simple Server (No Subprocess)

```python
from appinfra.app.fastapi import ServerBuilder

async def health():
    return {"status": "ok"}

async def hello(name: str):
    return {"message": f"Hello, {name}!"}

server = (ServerBuilder("simple-api")
    .with_port(8000)
    .routes
        .with_route("/health", health)
        .with_route("/hello/{name}", hello)
        .done()
    .build())

server.start()  # Blocking, runs uvicorn directly
```

### Example 2: Subprocess-Isolated Server with IPC

```python
from appinfra.app.fastapi import ServerBuilder
import multiprocessing as mp

# Create IPC queues
request_q: mp.Queue = mp.Queue()
response_q: mp.Queue = mp.Queue()

# Build server with subprocess mode
server = (ServerBuilder("worker-api")
    .with_host("0.0.0.0")
    .with_port(8000)
    .routes
        .with_route("/health", health_handler)
        .with_route("/process", process_handler, methods=["POST"])
        .with_router(my_router, prefix="/api/v1")
        .with_cors(origins=["http://localhost:3000"])
        .done()
    .subprocess
        .with_ipc(request_q, response_q)
        .with_log_file("/var/log/api.log")
        .with_max_pending(200)
        .done()
    .uvicorn
        .with_workers(4)
        .with_log_level("info")
        .with_access_log(True)
        .done()
    .build())

# Start API server in subprocess
proc = server.start_subprocess()
print(f"API server started (pid={proc.pid})")

# Main process handles requests via queues
shutdown = threading.Event()
while not shutdown.is_set():
    try:
        request = request_q.get(timeout=0.01)
        result = heavy_computation(request)
        response_q.put(result)
    except Empty:
        continue

# Cleanup
server.stop()
```

### Example 3: Integrated with AppBuilder

```python
from appinfra.app import AppBuilder
from appinfra.app.fastapi import ServerBuilder, ServerPlugin

# Build server configuration
server = (ServerBuilder("myapp-api")
    .with_port(8000)
    .routes
        .with_route("/health", health)
        .with_route("/api/data", get_data)
        .done()
    .subprocess
        .with_ipc(request_q, response_q)
        .done()
    .build())

# Integrate with CLI app
app = (AppBuilder("myapp")
    .with_description("My application with HTTP API")
    .tools
        .with_plugin(ServerPlugin(server))
        .with_tool(OtherTool())
        .done()
    .build())

app.run()
# CLI: myapp serve     -> starts HTTP server
# CLI: myapp other     -> runs other tool
```

### Example 4: Route Handler with IPC

```python
from fastapi import Depends
from appinfra.app.fastapi import IPCChannel

# Inside subprocess, route handlers use IPCChannel to talk to main process

async def get_ipc_channel() -> IPCChannel:
    """Dependency to get IPC channel."""
    return app.state.ipc_channel

@router.post("/inference")
async def inference(
    request: InferenceRequest,
    ipc: IPCChannel = Depends(get_ipc_channel),
):
    # Submit to main process and wait for response
    internal_request = InternalRequest(id=uuid4(), data=request.data)
    response = await ipc.submit(internal_request, timeout=60.0)

    if response.status == "error":
        raise HTTPException(500, response.error)

    return InferenceResponse(result=response.result)

@router.post("/inference/stream")
async def inference_stream(
    request: InferenceRequest,
    ipc: IPCChannel = Depends(get_ipc_channel),
):
    internal_request = InternalRequest(id=uuid4(), data=request.data, stream=True)

    async def generate():
        async for chunk in ipc.submit_streaming(internal_request):
            yield f"data: {chunk.token}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Reference Implementation

The inference server has a working implementation of these patterns that can be used as reference:

| Component | Reference File | Key Functions/Classes |
|-----------|---------------|----------------------|
| UvicornConfig | `inference/serving/dispatch/config.py:41-52` | `UvicornConfig` dataclass |
| ApiConfig | `inference/serving/dispatch/config.py:56-63` | `ApiConfig` dataclass |
| Subprocess spawn | `inference/serving/dispatch/main.py:230-246` | `_start_uvicorn()` |
| Graceful shutdown | `inference/serving/dispatch/main.py:194-203` | `_shutdown_uvicorn()` |
| Uvicorn kwargs builder | `inference/serving/api/process.py:28-47` | `_build_uvicorn_kwargs()` |
| Log isolation | `inference/serving/api/process.py:16-25` | `_setup_file_logging()` |
| Subprocess entry | `inference/serving/api/process.py:50-83` | `run_uvicorn()` |
| Response polling | `inference/serving/api/app.py:220-266` | `_poll_responses()` |
| Request tracking | `inference/serving/api/app.py:97-120` | `pending` dict, Future-based |
| Stream handling | `inference/serving/api/app.py:122-165` | `pending_streams`, async Queue |

---

## Implementation Notes

### Subprocess Log Isolation

When running in subprocess mode with `with_log_file()`:

```python
def _setup_subprocess_logging(log_file: str) -> None:
    """Isolate subprocess logging to dedicated file."""
    # Replace root logger handlers
    handler = logging.FileHandler(log_file)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)

    # Redirect stdout/stderr for libraries that print directly
    sys.stdout = open(log_file, "a")
    sys.stderr = sys.stdout
```

### Graceful Shutdown Pattern

```python
def _graceful_shutdown(proc: mp.Process, timeout: float = 5.0) -> None:
    """Terminate -> join(timeout) -> kill pattern."""
    proc.terminate()
    proc.join(timeout=timeout)
    if proc.is_alive():
        proc.kill()
        proc.join()
```

### Response Queue Polling (Async)

```python
async def _poll_responses(self) -> None:
    """Background task to poll response queue and resolve futures."""
    loop = asyncio.get_event_loop()

    while True:
        try:
            # Non-blocking get with executor
            item = await loop.run_in_executor(
                None,
                lambda: self.response_q.get(timeout=self._config.poll_interval),
            )

            # Dispatch based on type
            if hasattr(item, 'is_streaming') and item.is_streaming:
                await self._handle_stream_chunk(item)
            else:
                await self._handle_response(item)

        except Empty:
            await asyncio.sleep(0)  # Yield to event loop
            continue
        except asyncio.CancelledError:
            break
```

---

## Testing Requirements

1. **Unit tests** for each component (builder, config, runtime)
2. **Integration tests** for subprocess communication
3. **E2E tests** for full request/response cycle through IPC
4. **Stress tests** for max_pending limits and queue behavior

---

## Dependencies

Add to appinfra's dependencies:
- `fastapi` (already recommended in appinfra docs)
- `uvicorn`
- `starlette` (comes with fastapi)

---

## Migration Path

After implementation, the inference server can be migrated:

1. Replace config imports: `from appinfra.app.fastapi import ApiConfig, UvicornConfig`
2. Replace subprocess management with `ServerBuilder`
3. Replace manual IPC with `IPCChannel`
4. Reduce inference-specific code to just route handlers and business logic

---

## Questions for Implementers

1. Should `IPCChannel` support custom serialization (pickle alternatives)?
2. Should there be built-in health check route that reports IPC status?
3. Should `Server` support automatic subprocess restart on crash?
4. Integration with existing `appinfra.app.server` (experimental) - deprecate or keep separate?
