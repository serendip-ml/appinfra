# Infra Examples

Comprehensive examples demonstrating the infra framework's features. Examples are organized by topic
with a clear learning progression.

## Prerequisites

- Python 3.11+
- Virtual environment at `~/.venv` (see [Virtual Environment Setup](../docs/guides/virtual-environment.md))
- PostgreSQL 16 (only for database examples)

## Quick Start

```bash
# Ensure dependencies are installed
make setup

# Run any example with venv
~/.venv/bin/python examples/01_basics/hello_world.py

# Or activate venv first
source ~/.venv/bin/activate
python examples/01_basics/hello_world.py
```

## Learning Path

Follow this progression to learn the framework:

### 1. Basics → [01_basics/](01_basics/)
Start here to understand core concepts:
- `hello_world.py` - Minimal app with App class
- `hello_world_with_cfg.py` - Configuration and logging

### 2. App Framework → [02_app_framework/](02_app_framework/)
Learn application architecture patterns:
- `app_with_commands.py` - Command-based apps
- `app_with_tool.py` - Tool-based apps
- `app_with_subtools.py` - Tool groups and hierarchies
- `app_with_tool_builders.py` - Builder-based tool creation
- `app_with_ticker.py` - Background task execution

### 3. Logging → [03_logging/](03_logging/)
Master the logging system:
- `logging_builder_example.py` - Comprehensive logging examples
- `disabled_logging.py` - Disabling logging for tests
- `database_logging.py` - Logging to database

### 4. Configuration → [04_configuration/](04_configuration/)
Configuration management:
- `env_overrides_example.py` - Environment variable overrides

### 5. Database → [05_database/](05_database/)
PostgreSQL integration:
- `basic_critical_flush.py` - Basic critical flush pattern
- `advanced_critical_flush.py` - Advanced flush with real DB
- `pg_test_helper.py` - Database test helper
- `pg_test_helper_custom_config.py` - Custom config for tests

### 6. Advanced → [06_advanced/](06_advanced/)
Advanced topics and utilities:
- `generator_usage_example.py` - Generator methods
- `tcp_server.py` - TCP server with ticker
- `ticker_standalone.py` - Standalone ticker usage

### 8. Decorators → [08_decorators/](08_decorators/)
Decorator-based tool definitions:
- `simple_decorator.py` - Basic @tool decorator usage
- `hierarchical_commands.py` - Nested command groups
- `mixed_approach.py` - Combining decorators with classes

## Running Examples

All examples use the virtual environment at `~/.venv`.

**Method 1: Direct execution**
```bash
~/.venv/bin/python examples/01_basics/hello_world.py
```

**Method 2: Activate venv first**
```bash
source ~/.venv/bin/activate
python examples/01_basics/hello_world.py
deactivate
```

**Method 3: Make examples executable**
```bash
chmod +x examples/01_basics/hello_world.py
./examples/01_basics/hello_world.py  # Uses shebang: #!/usr/bin/env python3
```

Note: For direct execution, ensure `python3` resolves to your venv. See
[Virtual Environment Setup](../docs/guides/virtual-environment.md#running-scripts-directly).

## Examples by Feature

### Application Framework
- Command-based apps: `02_app_framework/app_with_commands.py`
- Tool-based apps: `02_app_framework/app_with_tool.py`
- Background tasks: `02_app_framework/app_with_ticker.py`

### Logging
- Console logging: `01_basics/hello_world_with_cfg.py`
- File logging: `03_logging/logging_builder_example.py`
- JSON logging: `03_logging/logging_builder_example.py`
- Database logging: `03_logging/database_logging.py`
- Disabled logging: `03_logging/disabled_logging.py`

### Configuration
- YAML config: `01_basics/hello_world_with_cfg.py`
- Environment overrides: `04_configuration/env_overrides_example.py`

### Database
- Critical flush pattern: `05_database/basic_critical_flush_example.py`
- Test helpers: `05_database/pg_test_helper.py`

### Time & Scheduling
- Periodic execution: `02_app_framework/app_with_ticker.py`
- Standalone ticker: `06_advanced/ticker_standalone.py`

### Network
- TCP server: `06_advanced/tcp_server.py`

### Decorators
- Simple decorator: `08_decorators/simple_decorator.py`
- Hierarchical commands: `08_decorators/hierarchical_commands.py`
- Mixed approach: `08_decorators/mixed_approach.py`

## Documentation

Each topic folder contains a README with detailed explanations:
- [01_basics/README.md](01_basics/README.md) - Getting started
- [02_app_framework/README.md](02_app_framework/README.md) - App patterns
- [03_logging/README.md](03_logging/README.md) - Logging guide
- [04_configuration/README.md](04_configuration/README.md) - Config management
- [05_database/README.md](05_database/README.md) - Database integration
- [06_advanced/README.md](06_advanced/README.md) - Advanced topics
- [08_decorators/README.md](08_decorators/README.md) - Decorator-based tools

## Related Documentation

- [Logging Builder Guide](../docs/guides/logging-builder.md)
- [Configuration-Based Logging](../docs/guides/config-based-logging.md)
- [PostgreSQL Test Helper](../docs/guides/pg-test-helper.md)
- [Environment Variable Overrides](../docs/guides/environment-variables.md)
- [Test Naming Standards](../docs/guides/test-naming-standards.md)

## Troubleshooting

### Virtual environment not found
```bash
# Install dependencies
cd /path/to/appinfra
make setup
```

### PostgreSQL connection errors (database examples only)
```bash
# Start PostgreSQL
make pg.server.up

# Verify connection
make pg
```

### Import errors
```bash
# Ensure you're in the project root
cd /path/to/appinfra

# Run from project root
python examples/01_basics/hello_world.py
```

## Contributing Examples

When adding new examples:
1. Place in appropriate topic folder
2. Use portable shebang: `#!/usr/bin/env python3`
3. Add clear docstring explaining purpose
4. Include usage instructions
5. Update this README's index
6. Update topic-specific README
