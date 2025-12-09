# FastAPI Server Framework

Production-ready FastAPI + Uvicorn server framework with subprocess isolation and queue-based IPC.

## Installation

```bash
pip install appinfra[fastapi]
```

## Quick Start

### Simple Server (Direct Mode)

```python
from appinfra.app.fastapi import ServerBuilder

async def health():
    return {"status": "ok"}

server = (ServerBuilder("myapi")
    .with_port(8000)
    .routes.with_route("/health", health).done()
    .build())

server.start()  # Blocking
```

### Subprocess Mode with IPC

For CPU-intensive work, run the API server in a subprocess while the main process handles
computation:

```python
import multiprocessing as mp
from appinfra.app.fastapi import ServerBuilder

request_q, response_q = mp.Queue(), mp.Queue()

server = (ServerBuilder("worker-api")
    .with_port(8000)
    .routes.with_route("/health", health).done()
    .subprocess
        .with_ipc(request_q, response_q)
        .with_auto_restart(enabled=True)
        .done()
    .build())

proc = server.start_subprocess()  # Non-blocking

# Main process handles requests
while True:
    request = request_q.get()
    result = process(request)
    response_q.put(result)
```

### AppBuilder Integration

```python
from appinfra.app import AppBuilder
from appinfra.app.fastapi import ServerBuilder, ServerPlugin

server = ServerBuilder("myapi").with_port(8000).build()

app = (AppBuilder("myapp")
    .tools.with_plugin(ServerPlugin(server)).done()
    .build())

# CLI: myapp serve
```

## ServerBuilder

Fluent builder for configuring FastAPI servers.

```python
from appinfra.app.fastapi import ServerBuilder

server = (ServerBuilder("myapi")
    # Server binding
    .with_host("0.0.0.0")
    .with_port(8000)

    # OpenAPI metadata
    .with_title("My API")
    .with_description("API description")
    .with_version("1.0.0")

    # Timeouts
    .with_timeout(30.0)

    # Bulk configuration
    .with_config(ApiConfig(...))

    .build())
```

### Route Configuration

Access via `.routes`:

```python
server = (ServerBuilder("myapi")
    .routes
        # Simple route
        .with_route("/health", health_handler)

        # Route with methods
        .with_route("/data", data_handler, methods=["POST", "PUT"])

        # Include a router
        .with_router(api_router, prefix="/api/v1", tags=["v1"])

        # CORS
        .with_cors(
            origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST"]
        )

        # Middleware
        .with_middleware(CustomMiddleware, timeout=30)

        # Exception handlers
        .with_exception_handler(ValueError, error_handler)

        .done()
    .build())
```

### Subprocess Configuration

Access via `.subprocess`:

```python
server = (ServerBuilder("myapi")
    .subprocess
        # IPC queues (required for subprocess mode)
        .with_ipc(request_q, response_q)

        # Auto-restart on crash
        .with_auto_restart(enabled=True, delay=2.0, max_restarts=10)

        # Log isolation
        .with_log_file("/var/log/api.log")

        # IPC tuning
        .with_poll_interval(0.01)      # Response polling (10ms)
        .with_response_timeout(30.0)   # Per-request timeout
        .with_max_pending(200)         # Max concurrent requests
        .with_health_reporting(True)   # Include IPC in health endpoint

        # Or bulk config
        .with_config(IPCConfig(...))

        .done()
    .build())
```

### Uvicorn Configuration

Access via `.uvicorn`:

```python
server = (ServerBuilder("myapi")
    .uvicorn
        .with_workers(4)
        .with_log_level("info")
        .with_access_log(True)
        .with_ssl("/path/to/key.pem", "/path/to/cert.pem")
        .with_timeout_keep_alive(30)
        .with_limit_concurrency(100)
        .with_limit_max_requests(1000)
        .with_backlog(4096)

        # Or bulk config
        .with_config(UvicornConfig(...))

        .done()
    .build())
```

## Server

Runtime server instance returned by `ServerBuilder.build()`.

```python
server = ServerBuilder("myapi").build()

# Properties
server.name              # Server name
server.config            # ApiConfig
server.app               # FastAPI instance (built on first access)
server.is_subprocess_mode  # True if IPC queues configured
server.is_running        # True if subprocess is alive
server.request_queue     # Request queue (subprocess mode)
server.response_queue    # Response queue (subprocess mode)

# Methods
server.start()           # Run server (blocking)
server.start_subprocess()  # Start in subprocess (non-blocking, returns Process)
server.stop()            # Stop subprocess
```

## IPCChannel

Async IPC for FastAPI route handlers to communicate with the main process.

```python
from fastapi import Request

async def process_handler(request: Request):
    ipc: IPCChannel = request.app.state.ipc_channel

    # Submit request and wait for response
    response = await ipc.submit(
        request_id="unique-id",
        request={"data": "..."},
        timeout=30.0  # Optional, defaults to config
    )

    return response
```

### Streaming Responses

```python
from fastapi.responses import StreamingResponse

async def stream_handler(request: Request):
    ipc: IPCChannel = request.app.state.ipc_channel

    async def generate():
        async for chunk in ipc.submit_streaming("req-id", {"prompt": "..."}):
            yield chunk.data
            if chunk.is_final:
                break

    return StreamingResponse(generate())
```

## Configuration Classes

### ApiConfig

Main server configuration:

```python
from appinfra.app.fastapi import ApiConfig, UvicornConfig, IPCConfig

config = ApiConfig(
    # Server binding
    host="0.0.0.0",           # Bind address
    port=8000,                # Bind port

    # OpenAPI metadata
    title="My API",           # API title
    description="...",        # API description
    version="1.0.0",          # API version

    # Subprocess settings
    response_timeout=60.0,    # Default timeout (when no IPC)
    log_file="/var/log/api.log",  # Subprocess log file
    auto_restart=True,        # Restart on crash
    restart_delay=1.0,        # Delay before restart
    max_restarts=5,           # Max restarts (0=unlimited)

    # Nested configs
    uvicorn=UvicornConfig(...),
    ipc=IPCConfig(...),       # None = direct mode
)
```

### UvicornConfig

Uvicorn server settings:

```python
from appinfra.app.fastapi import UvicornConfig

config = UvicornConfig(
    workers=4,                # Worker processes
    timeout_keep_alive=5,     # Keep-alive timeout
    limit_concurrency=None,   # Max concurrent connections
    limit_max_requests=None,  # Max requests per worker
    backlog=2048,             # Socket backlog
    log_level="warning",      # Log level
    access_log=False,         # Access logging
    ssl_keyfile=None,         # SSL key path
    ssl_certfile=None,        # SSL cert path
)
```

### IPCConfig

IPC behavior settings:

```python
from appinfra.app.fastapi import IPCConfig

config = IPCConfig(
    poll_interval=0.01,       # Response polling (10ms = 100 polls/sec)
    response_timeout=60.0,    # Default request timeout
    max_pending=100,          # Max pending requests
    enable_health_reporting=True,  # IPC status in health endpoint
)
```

## ServerPlugin

Integrates server with AppBuilder for CLI apps:

```python
from appinfra.app import AppBuilder
from appinfra.app.fastapi import ServerBuilder, ServerPlugin

server = ServerBuilder("myapi").with_port(8000).build()

app = (AppBuilder("myapp")
    .tools.with_plugin(ServerPlugin(server)).done()
    .build())
```

This adds a `serve` command to your CLI:

```bash
myapp serve              # Start server
myapp serve --port 9000  # Override port
```

## Architecture

```
┌─────────────────┐     mp.Queue      ┌──────────────────┐
│   Main Process  │ ◄───────────────► │   FastAPI        │
│                 │    request_q       │   Subprocess     │
│  - Heavy compute│    response_q     │                  │
│  - ML inference │                   │  - HTTP handling │
│  - Data loading │                   │  - Routing       │
└─────────────────┘                   │  - Validation    │
                                      └──────────────────┘
```

**Why subprocess isolation?**

- Python GIL: CPU-bound work in main process doesn't block HTTP handling
- Memory isolation: API server crashes don't affect main process
- Auto-restart: Server recovers from crashes automatically
- Log isolation: Separate log files for debugging

## See Also

- [Application Framework](app.md) - Core application classes
- [AppBuilder](app-builder.md) - Fluent builder API
