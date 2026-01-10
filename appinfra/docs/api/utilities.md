# Utilities

Core utilities including DotDict, Config, rate limiting, EWMA, size formatting, and YAML support.

## Config

Configuration loader with environment variable overrides.

```python
class Config(DotDict):
    def __init__(
        self,
        fname: str,
        enable_env_overrides: bool = True,
        env_prefix: str = "INFRA_",
        merge_strategy: str = "replace"
    ): ...

    def get(self, path: str, default=None) -> Any: ...
    def get_env_overrides(self) -> dict: ...
```

**Usage:**

```python
from appinfra.config import Config, get_config_file_path

config = Config(get_config_file_path())  # Automatic etc/ resolution

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
config = Config(get_config_file_path())
print(config.logging.level)  # "debug" (from env)
```

## DotDict

Dictionary subclass with attribute-style access and dot-notation paths.

Since DotDict subclasses `dict`, `isinstance(dotdict, dict)` returns `True`.

```python
class DotDict(dict):
    def __init__(self, **kwargs): ...

    def get(self, path: str, default=None) -> Any: ...  # Dot-path access, returns None if not found
    def require(self, path: str) -> Any: ...            # Like get(), but raises if path missing
    def has(self, path: str) -> bool: ...               # Check if path exists
    def set(self, **kwargs) -> DotDict: ...
    def dict(self) -> dict: ...
    def to_dict(self) -> dict: ...                      # Recursive conversion to plain dicts
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

# isinstance check works (DotDict is a dict subclass)
isinstance(config, dict)  # True
isinstance(config.database, dict)  # True

# Attribute access
print(config.database.host)  # "localhost"

# Dictionary access
print(config["database"]["port"])  # 5432

# Dot-path get (cleaner than chained .get() calls)
# Instead of: config.get("database", {}).get("host", {}).get("port")
value = config.get("database.host")           # "localhost"
port = config.get("database.port", 5432)      # 5432
missing = config.get("database.missing")      # None

# Require - raises DotDictPathNotFoundError if path missing
from appinfra.dot_dict import DotDictPathNotFoundError
try:
    host = config.require("database.host")    # "localhost"
    user = config.require("database.user")    # Raises!
except DotDictPathNotFoundError as e:
    print(f"Missing required config: {e.path}")

# Check if path exists (useful when None could be a valid value)
if config.has("database.password"):
    password = config.get("database.password")

# Set values
config.database.username = "postgres"

# Convert to dict
data = config.dict()       # One level conversion
data = config.to_dict()    # Recursive conversion
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

## Size Formatting

Format byte sizes as human-readable strings.

```python
from appinfra.size import size_str, size_to_bytes

# Format bytes to string
size_str(1024)           # "1KB"
size_str(1536)           # "1.5KB"
size_str(1048576)        # "1MB"
size_str(500)            # "500B"

# Precise mode (3 decimal places)
size_str(1536, precise=True)   # "1.500KB"

# SI units (1000-based instead of 1024)
size_str(1500, binary=False)   # "1.5KB"

# Parse size string back to bytes
size_to_bytes("1.5MB")   # 1572864
size_to_bytes("500B")    # 500
size_to_bytes("1GiB")    # 1073741824 (IEC suffixes supported)
```

**Options:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `precise` | `False` | Show 3 decimal places |
| `binary`  | `True`  | Use 1024-based (binary) vs 1000-based (SI) |

**Validation:**

```python
from appinfra.size import validate_size, InvalidSizeError

validate_size(1024)    # True
validate_size(-1)      # False
validate_size("1KB")   # False (not a number)

try:
    size_str(-1)
except InvalidSizeError as e:
    print(f"Invalid: {e}")
```

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

**`!path`** - Resolve paths relative to config file location with tilde expansion:

```yaml
models_dir: !path ../.models       # Resolves to absolute path
data_dir: !path /absolute/path     # Absolute paths unchanged
cache: !path ./cache               # Relative to config file
home_cache: !path ~/.cache/myapp   # Expands ~ to home directory
```

## Path Resolution

Path resolution in configuration files requires the explicit `!path` YAML tag. Without the tag,
paths remain as literal strings:

```yaml
# Config at /app/etc/config.yaml
logging:
  file: ./logs/app.log           # Stays as "./logs/app.log" (literal string)
  resolved: !path ./logs/app.log # Resolved to /app/etc/logs/app.log

cache:
  dir: ~/.cache/myapp            # Stays as "~/.cache/myapp" (literal string)
  resolved: !path ~/.cache/myapp # Expands to /home/user/.cache/myapp
```

```python
from appinfra.config import Config, get_config_file_path

config = Config(get_config_file_path("config.yaml"))
print(config.logging.file)      # "./logs/app.log" (literal)
print(config.logging.resolved)  # "/app/etc/logs/app.log" (absolute)
```

**The `!path` tag:**
- Resolves relative paths (`./`, `../`) to absolute paths based on config file location
- Expands tilde (`~`) to the user's home directory
- Leaves absolute paths and URLs unchanged

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
