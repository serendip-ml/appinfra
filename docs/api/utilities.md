# Utilities

Core utilities including DotDict, Config, rate limiting, EWMA, and YAML support.

## Config

Configuration loader with environment variable overrides.

```python
class Config(DotDict):
    def __init__(
        self,
        config_path: str,
        resolve_paths: bool = True  # Resolve relative paths
    ): ...

    def get(self, path: str, default=None) -> Any: ...
    def get_env_overrides(self) -> dict: ...
```

**Usage:**

```python
from appinfra.app.cfg import Config

config = Config("etc/infra.yaml")

# Access with dot notation
print(config.logging.level)
print(config.database.host)

# Get with fallback
port = config.get("database.port", default=5432)
```

**Environment Override Pattern:**

```bash
export INFRA_LOGGING_LEVEL=debug
export INFRA_DATABASE_PORT=5433
```

```python
config = Config("etc/infra.yaml")
print(config.logging.level)  # "debug" (from env)
```

## DotDict

Dictionary with attribute-style access and dot-notation paths.

```python
class DotDict:
    def __init__(self, **kwargs): ...

    def get(self, path: str, default=None) -> Any: ...  # Returns None if not found
    def has(self, path: str) -> bool: ...               # Check if path exists
    def set(self, **kwargs) -> DotDict: ...
    def dict(self) -> dict: ...
    def keys() -> KeysView: ...
    def values() -> ValuesView: ...
    def items() -> ItemsView: ...
```

**Usage:**

```python
from appinfra.dot_dict import DotDict

# Initialize with keyword arguments
config = DotDict(
    database={"host": "localhost", "port": 5432}
)

# Or from existing dict
data = {"database": {"host": "localhost"}}
config = DotDict(**data)

# Attribute access
print(config.database.host)  # "localhost"

# Dictionary access
print(config["database"]["port"])  # 5432

# Get with path (returns None if not found, like dict.get())
value = config.get("database.host")      # "localhost"
missing = config.get("database.missing") # None
fallback = config.get("missing", "default")  # "default"

# Check if path exists (useful when None could be a valid value)
if config.has("database.password"):
    password = config.get("database.password")

# Set values
config.database.username = "postgres"

# Convert to dict
data = config.dict()
```

## RateLimiter

Control operation frequency.

```python
class RateLimiter:
    def __init__(
        self,
        max_calls: int,      # Maximum calls allowed
        period: float        # Time period in seconds
    ): ...

    def __enter__(self): ...
    def __exit__(self, ...): ...
    def acquire(self) -> None: ...
```

**Usage:**

```python
from appinfra.rate_limit import RateLimiter
import time

# Allow 5 calls per 10 seconds
limiter = RateLimiter(max_calls=5, period=10.0)

for i in range(10):
    with limiter:
        print(f"Call {i}")
        # Blocks after 5 calls until period resets
```

## EWMA

Exponentially Weighted Moving Average for streaming values.

```python
class EWMA:
    def __init__(self, age: float = 30.0): ...

    def add(self, value: float) -> None: ...   # Add sample
    def value(self) -> float: ...              # Get current average
    def reset(self, value: float = 0.0): ...   # Reset state
```

The `age` parameter controls smoothing:
- Higher age = smoother output, slower to react to changes
- Lower age = noisier output, faster to react to changes

**Usage:**

```python
from appinfra.ewma import EWMA

# Track average request latency with 30-second smoothing
latency = EWMA(age=30.0)
latency.add(0.05)  # 50ms
latency.add(0.08)  # 80ms
latency.add(0.03)  # 30ms
print(f"Average latency: {latency.value():.3f}s")

# Reset to start fresh
latency.reset()
```

**How it works:**

EWMA uses the formula: `avg = (new * decay) + (avg * (1 - decay))` where `decay = 2 / (age + 1)`.

The first sample sets the initial value directly. Subsequent samples blend with exponential
weighting, giving more weight to recent values.

## YAML Utilities

YAML loading with custom tag support.

```python
from appinfra.yaml import load, Loader
from pathlib import Path

# Load YAML with custom tag support
with open("config.yaml") as f:
    config = load(f, current_file=Path("config.yaml"))
```

### Custom Tags

**`!include`** - Include other YAML files:

```yaml
# Key-level include (as a value)
database: !include "./database.yaml"           # Include entire file
settings: !include "config.yaml#app.settings"  # Include specific section

# Document-level include (merge at root)
!include "./base.yaml"

app_name: myapp
server:
  port: 8080
```

Document-level includes (at column 0) merge included content with the main document. The included
file provides defaults; main document content overrides. Nested includes are supported.

**`!secret`** - Mark sensitive values (warns if not using env var syntax):

```yaml
password: !secret ${DB_PASSWORD}    # Valid - env var reference
api_key: !secret my_literal_key     # Warning - should use ${VAR} syntax
```

**`!path`** - Resolve paths relative to config file location:

```yaml
models_dir: !path ../.models       # Resolves to absolute path
data_dir: !path /absolute/path     # Absolute paths unchanged
cache: !path ./cache               # Relative to config file
```

## Path Resolution

Relative paths in config are resolved automatically:

```yaml
# Config at /app/etc/config.yaml
logging:
  file: ./logs/app.log     # Resolves to /app/etc/logs/app.log
```

```python
config = Config("etc/config.yaml", resolve_paths=True)
print(config.logging.file)  # Absolute path
```

## Utility Functions

```python
from appinfra.utils import pretty, is_int

# Pretty print data structures
data = {"name": "John", "nested": {"key": "value"}}
print(pretty(data))

# Check if value is integer-like
is_int("123")   # True
is_int("12.3")  # False
```

## Deprecation Decorator

```python
from appinfra.deprecation import deprecated

@deprecated(version="0.2.0", replacement="new_function")
def old_function():
    return "old result"

old_function()  # Warning: old_function is deprecated since 0.2.0
```

## See Also

- [Environment Variables Guide](../guides/environment-variables.md)
- [Configuration examples](../examples/)
