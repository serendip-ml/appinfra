# Logging System

Comprehensive logging with structured output, custom levels, and multiple handlers.

## Log Levels

| Level | Value | Description |
|-------|-------|-------------|
| `trace2` | 4 | Most detailed tracing |
| `trace` | 5 | Detailed tracing |
| `debug` | 10 | Debug messages |
| `info` | 20 | Informational |
| `warning` | 30 | Warnings |
| `error` | 40 | Errors |
| `critical` | 50 | Critical errors |
| `False` | - | Disable logging completely |

## LoggingBuilder

Fluent API for configuring loggers.

```python
class LoggingBuilder:
    def __init__(self, name: str): ...

    def with_level(self, level: str | bool) -> LoggingBuilder: ...
    def with_location(self, level: int) -> LoggingBuilder: ...  # 0=none, 1=file:line, 2=full
    def with_micros(self, enabled: bool = True) -> LoggingBuilder: ...
    def console_handler(self, **kwargs) -> LoggingBuilder: ...
    def file_handler(self, path: str, **kwargs) -> LoggingBuilder: ...
    def build(self) -> Logger: ...
```

**Basic Example:**

```python
from appinfra.log import LoggingBuilder

logger = (
    LoggingBuilder("my_app")
    .with_level("info")
    .console_handler()
    .build()
)

logger.info("Application started")
logger.debug("Debug message")  # Won't show (level is info)
```

## LogConfig

Configuration dataclass for logging.

```python
@dataclass
class LogConfig:
    level: str | bool = "info"     # Log level or False to disable
    location: int = 0              # File location in output (0, 1, 2)
    micros: bool = False           # Microsecond timestamps
    topic: str | None = None       # Topic filter
    console: bool = True           # Enable console output
    file: str | None = None        # Log file path
    max_bytes: int = 10_485_760    # Max file size (10MB)
    backup_count: int = 5          # Number of backup files
```

## LoggerFactory

Factory for creating and managing loggers.

```python
class LoggerFactory:
    @staticmethod
    def create_root(config: LogConfig) -> Logger: ...

    @staticmethod
    def derive(parent: Logger, name: str) -> Logger: ...

    @staticmethod
    def create_with_separator(name: str, prefix: str = "") -> Logger: ...
```

## File Logging with Rotation

```python
from appinfra.log import LoggingBuilder

logger = (
    LoggingBuilder("my_app")
    .with_level("debug")
    .console_handler()
    .file_handler(
        "logs/app.log",
        max_bytes=10*1024*1024,  # 10MB
        backup_count=5
    )
    .build()
)
```

## JSON Structured Logging

```python
from appinfra.log.builder import JSONLoggingBuilder

logger = (
    JSONLoggingBuilder("my_app")
    .with_level("info")
    .console_handler()
    .build()
)

logger.info("User logged in", extra={
    "user_id": "123",
    "ip_address": "192.168.1.1"
})
```

## Quick Setup Functions

One-line logger creation:

```python
from appinfra.log import quick_console_logger, quick_file_logger, quick_both_logger

# Console only
logger = quick_console_logger("myapp", level="info")

# File only
logger = quick_file_logger("myapp", "logs/app.log")

# Console + file
logger = quick_both_logger("myapp", "logs/app.log", level="info")
```

## Capturing Third-Party Loggers

Unify all Python logging (including third-party libraries) with appinfra's formatting:

```python
from appinfra.log import capture_all_loggers

# Capture all loggers at INFO level
capture_all_loggers(level="info")

# Now logs from torch, httpx, vllm, etc. use appinfra format
import torch  # Its logs will now use appinfra formatting
```

**Parameters:**

```python
capture_all_loggers(
    level="info",           # Log level (or False to disable all logging)
    clear_handlers=True,    # Remove existing handlers from all loggers
    colors=True,            # Enable colored console output
    location=False,         # Show file locations in log messages
    micros=False,           # Microsecond precision in timestamps
)
```

**Preserve existing handlers:**

```python
# Keep library-specific handlers, but ensure propagation to root
capture_all_loggers(level="debug", clear_handlers=False)
```

**Pre-capture specific loggers:**

Some libraries create loggers after `capture_all_loggers()` runs. Use `capture_logger()` to
pre-configure them:

```python
from appinfra.log import capture_all_loggers, capture_logger

capture_all_loggers(level="info")

# Pre-capture before import - logger will be ready when library uses it
capture_logger("flashinfer", level="warning")
capture_logger("vllm.engine")

import flashinfer  # Logger already configured with appinfra formatting
```

## Topic-Based Logging

Different log levels for different subsystems:

```python
from appinfra.log import LogLevelManager, LoggingBuilder

# Set different levels for different topics
level_mgr = LogLevelManager.get_instance()
level_mgr.set_level("/infra/db", "debug")
level_mgr.set_level("/infra/app", "info")

# Create logger with topic
logger = LoggingBuilder("/infra/db").console_handler().build()
logger.debug("Database query")  # Will show (debug level for /infra/db)
```

## Disabling Logging

```python
from appinfra.log import LoggingBuilder

# Method 1: with_level(False)
logger = LoggingBuilder("my_app").with_level(False).build()

# Method 2: via config
# INFRA_LOGGING_LEVEL=false
```

## CallbackRegistry

Register callbacks for log events:

```python
from appinfra.log import CallbackRegistry, listens_for

@listens_for("error")
def on_error(record):
    # Handle error log events
    send_alert(record.getMessage())

# Or manually
CallbackRegistry.register("error", my_callback)
```

## See Also

- [Logging Builder Guide](../guides/logging-builder.md) - Comprehensive guide
- [Config-Based Logging](../guides/config-based-logging.md) - YAML configuration
