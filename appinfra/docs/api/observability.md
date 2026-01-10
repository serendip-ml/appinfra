# Observability

Simple callback-based hooks for monitoring framework operations without requiring external
dependencies like OpenTelemetry.

## ObservabilityHooks

Central registry for event callbacks.

```python
class ObservabilityHooks:
    def __init__(self): ...

    def register(self, event: HookEvent, callback: Callable[[HookContext], None]) -> None: ...
    def on(self, event: HookEvent) -> Callable: ...  # Decorator
    def register_global(self, callback: Callable[[HookContext], None]) -> None: ...
    def unregister(self, event: HookEvent, callback: Callable) -> bool: ...
    def clear(self, event: HookEvent | None = None) -> None: ...
    def trigger(self, event: HookEvent, **kwargs) -> None: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
```

**Basic Usage:**

```python
import logging
from appinfra.observability import ObservabilityHooks, HookEvent, HookContext

lg = logging.getLogger(__name__)
hooks = ObservabilityHooks()

# Register with decorator
@hooks.on(HookEvent.QUERY_START)
def log_query_start(context: HookContext):
    lg.info(f"Query started: {context.query}")

# Or register directly
hooks.register(HookEvent.QUERY_END, lambda ctx: lg.info(f"Query took {ctx.duration}s"))

# Trigger from framework code
hooks.trigger(HookEvent.QUERY_START, query="SELECT * FROM users")
```

## HookEvent

Event types for different framework operations.

```python
class HookEvent(Enum):
    # Database events
    QUERY_START = "query_start"
    QUERY_END = "query_end"
    CONNECTION_START = "connection_start"
    CONNECTION_END = "connection_end"

    # HTTP/Server events
    REQUEST_START = "request_start"
    REQUEST_END = "request_end"

    # Application/Tool events
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    APP_START = "app_start"
    APP_END = "app_end"

    # Lifecycle events
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
```

## HookContext

Context information passed to callbacks.

```python
@dataclass
class HookContext:
    event: HookEvent
    timestamp: float           # time.time() when created
    data: dict[str, Any]       # Event-specific data

    # Optional event-specific fields
    query: str | None = None
    duration: float | None = None
    error: Exception | None = None
    tool_name: str | None = None
    request_path: str | None = None
    response_code: int | None = None

    def set_duration(self) -> None: ...  # Calculate duration from start_time
```

## Global Callbacks

Register a callback that receives all events:

```python
import logging

lg = logging.getLogger(__name__)
hooks = ObservabilityHooks()

# Log all events
hooks.register_global(lambda ctx: lg.debug(f"Event: {ctx.event.value}"))
```

## Metrics Integration Example

Integrate with your metrics system:

```python
from appinfra.observability import ObservabilityHooks, HookEvent, HookContext

hooks = ObservabilityHooks()

# Track query latency
@hooks.on(HookEvent.QUERY_END)
def track_query_latency(ctx: HookContext):
    if ctx.duration:
        metrics.histogram("db.query.duration", ctx.duration)

# Track request counts
@hooks.on(HookEvent.REQUEST_END)
def track_requests(ctx: HookContext):
    metrics.counter("http.requests.total", tags={
        "path": ctx.request_path,
        "status": ctx.response_code
    })
```

## Tracing Integration Example

Integrate with distributed tracing:

```python
from appinfra.observability import ObservabilityHooks, HookEvent, HookContext

hooks = ObservabilityHooks()
active_spans = {}

@hooks.on(HookEvent.QUERY_START)
def start_db_span(ctx: HookContext):
    span = tracer.start_span("db.query")
    span.set_attribute("db.statement", ctx.query)
    active_spans[id(ctx)] = span

@hooks.on(HookEvent.QUERY_END)
def end_db_span(ctx: HookContext):
    span = active_spans.pop(id(ctx), None)
    if span:
        if ctx.error:
            span.record_exception(ctx.error)
        span.end()
```

## Enable/Disable Hooks

Temporarily disable hooks for performance:

```python
hooks = ObservabilityHooks()

# Check status
if hooks.enabled:
    print("Hooks are active")

# Disable for performance-critical sections
hooks.disable()
try:
    # High-frequency operations without hook overhead
    for i in range(10000):
        do_work()
finally:
    hooks.enable()
```

## Query Callbacks

Check if any callbacks are registered:

```python
# Check for specific event
if hooks.has_callbacks(HookEvent.QUERY_START):
    # Do extra work only if someone is listening
    hooks.trigger(HookEvent.QUERY_START, query=sql)

# Get all callbacks for an event
callbacks = hooks.get_callbacks(HookEvent.QUERY_END)
```

## Clear Callbacks

Remove registered callbacks:

```python
# Clear specific event
hooks.clear(HookEvent.QUERY_START)

# Clear all callbacks
hooks.clear()
```

## Error Handling

Hook callbacks that raise exceptions are caught and logged to stderr, preventing them from
interrupting framework operations:

```python
@hooks.on(HookEvent.QUERY_START)
def buggy_callback(ctx: HookContext):
    raise ValueError("Oops!")

# This still works - error is logged but doesn't propagate
hooks.trigger(HookEvent.QUERY_START, query="SELECT 1")
# stderr: "Error in observability hook for query_start: Oops!"
```

## Duration Tracking

Track operation duration using `set_duration()`:

```python
# Framework code pattern
ctx = HookContext(event=HookEvent.QUERY_START, query=sql)
hooks.trigger(HookEvent.QUERY_START, **ctx.data)

# ... perform query ...

ctx.set_duration()  # Calculates duration from start_time
hooks.trigger(HookEvent.QUERY_END, duration=ctx.duration, query=sql)
```

## See Also

- [Logging System](logging.md) - Structured logging
- [Database](database.md) - Database operations that emit hooks
