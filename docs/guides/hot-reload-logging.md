# Hot-Reload Logging Configuration

Automatically reload logging configuration when config files change, without restarting your
application. Useful for adjusting log levels and display options in long-running services.

## Installation

Hot-reload requires the optional `watchdog` dependency:

```bash
pip install appinfra[hotreload]
```

## Quick Start

### Via AppBuilder

```python
from appinfra.app.builder import AppBuilder

app = (
    AppBuilder("my-service")
    .config("etc/config.yaml")  # Load config with path tracking
    .logging()
        .with_level("info")
        .with_hot_reload(True)  # Enable hot-reload using config path
        .done()
    .build()
)
```

### Via Configuration File

```yaml
# etc/config.yaml
logging:
  level: info
  location: 1
  colors: true
  location_color: gray-15

  hot_reload:
    enabled: true
    debounce_ms: 500  # Wait 500ms after file change before reloading
```

## Configuration Options

### YAML Configuration

```yaml
logging:
  # Standard logging options (can be hot-reloaded)
  level: debug           # Log level: trace2, trace, debug, info, warning, error, critical
  location: 2            # File location depth (0=none, 1=file:line, 2=full path)
  micros: true           # Microsecond timestamp precision
  colors: true           # Enable colored output
  location_color: cyan   # Color for file location (e.g., gray-15, cyan, magenta)

  # Topic-based log levels (can be hot-reloaded)
  topics:
    /db.*: debug         # Database logs at debug level
    /api.*: info         # API logs at info level
    /auth.*: warning     # Auth logs at warning level

  # Hot-reload settings
  hot_reload:
    enabled: true
    debounce_ms: 500     # Debounce rapid file changes (default: 500ms)
```

### Programmatic Configuration

```python
app = (
    AppBuilder("my-service")
    .logging()
        .with_hot_reload(
            enabled=True,
            config_path="etc/logging.yaml",  # Explicit path (optional if .config() was called)
            section="logging",               # Config section to read (default: "logging")
            debounce_ms=1000                 # Debounce interval in milliseconds
        )
        .done()
    .build()
)
```

## What Can Be Hot-Reloaded

| Setting | Hot-Reloadable | Notes |
|---------|----------------|-------|
| `level` | Yes | Global log level |
| `location` | Yes | File location depth |
| `micros` | Yes | Timestamp precision |
| `colors` | Yes | Color output toggle |
| `location_color` | Yes | Location text color |
| `topics` | Yes | Topic-based log levels |
| File handlers | No | Requires restart |
| Handler paths | No | Requires restart |

## How It Works

1. **File Watcher**: Uses `watchdog` to monitor config files for changes
2. **Include Tracking**: Automatically watches all included files (via `!include` tags)
3. **Debouncing**: Waits for `debounce_ms` after last change to avoid rapid reloads
4. **Registry Update**: Updates all active `LogConfigHolder` instances atomically
5. **Thread-Safe**: All updates are thread-safe using locks

### Watching Included Files

If your logging configuration uses `!include` to split configs across files, **all included files
are automatically watched**. Modifying any file in the include chain triggers a reload:

```yaml
# etc/config.yaml (watched)
logging: !include "./logging.yaml"

# etc/logging.yaml (also watched!)
level: info
handlers: !include "./handlers.yaml"

# etc/handlers.yaml (also watched!)
console:
  type: console
  enabled: true
```

Editing `handlers.yaml` will trigger a hot-reload, even though it's nested two levels deep.

### Architecture

```
Config File Change
       ↓
   LogConfigWatcher (watchdog)
       ↓ (debounced)
   LogConfigRegistry.update_all()
       ↓
   LogConfigHolder.update() (for each holder)
       ↓
   Formatters read new config on next log
```

## Manual Reload

Force an immediate config reload without waiting for file changes:

```python
from appinfra.log.watcher import LogConfigWatcher

watcher = LogConfigWatcher.get_instance()
watcher.reload_now()
```

## Reload Callbacks

Register callbacks to be notified when config reloads:

```python
from appinfra.log.watcher import LogConfigWatcher

def on_config_reload(new_config):
    print(f"Log level changed to: {new_config.level}")

watcher = LogConfigWatcher.get_instance()
watcher.add_reload_callback(on_config_reload)
```

## Example: Dynamic Log Level Adjustment

```yaml
# etc/config.yaml - Initial state
logging:
  level: info
  hot_reload:
    enabled: true
```

```python
# my_service.py
from appinfra.app.builder import AppBuilder

app = (
    AppBuilder("my-service")
    .config("etc/config.yaml")
    .logging()
        .with_hot_reload(True)
        .done()
    .build()
)

# Application runs with INFO level...

# Edit etc/config.yaml while running:
# logging:
#   level: debug

# Logs automatically switch to DEBUG level without restart!
```

## Troubleshooting

### Hot-reload not working

1. **Check watchdog is installed**: `pip install appinfra[hotreload]`
2. **Verify config path**: Ensure the path is correct and file exists
3. **Check debounce**: Try reducing `debounce_ms` for faster response
4. **Check logs**: Look for "hot-reload watcher started" debug message

### Performance considerations

- File watching has minimal overhead (OS-level notifications)
- Debouncing prevents excessive reloads
- Config parsing only happens on actual changes
- Thread-safe updates don't block logging

## See Also

- [Logging System](../api/logging.md) - Full logging API reference
- [AppBuilder](../api/app-builder.md) - Application builder documentation
- [Config-Based Logging](config-based-logging.md) - YAML configuration basics
