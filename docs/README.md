# appinfra User Guide

Production-grade Python infrastructure framework providing reusable building blocks for robust
applications.

## Overview

A comprehensive toolkit of battle-tested infrastructure components extracted from many years of
systems programming experience. Designed for building reliable, high-performance Python applications
with clean abstractions and production-ready patterns.

## Scope & Philosophy

This framework provides **low-level infrastructure components** for building production Python
applications. It's designed for composability and reliability, not as a batteries-included web
framework.

| | |
|---|---|
| **In Scope** | Logging infrastructure, PostgreSQL abstraction, CLI framework, lifecycle management, time utilities |
| **Out of Scope** | Web frameworks, ORMs, async-native patterns, multi-database support |
| **Best For** | Production CLI tools, background services, systems-level Python applications |
| **Not For** | REST APIs (use FastAPI/Flask), async-heavy apps, general web development |

## Key Features

### Logging (`appinfra/log/`)

Advanced logging system with structured output:
- Custom log levels (TRACE/TRACE2)
- Multiple handlers (console, file rotation, database)
- Fluent builder API
- JSON structured logging
- Microsecond precision timestamps
- Hot-reload configuration (change log settings without restart)

### Database Layer (`appinfra/db/`)

PostgreSQL interface with SQLAlchemy:
- Connection pooling
- Query logging and performance monitoring
- Read-only connection support
- Migration support
- Test helpers

### Application Framework (`appinfra/app/`)

Modern framework for CLI tools and applications:
- Fluent AppBuilder API
- Tool registry and protocols
- Server framework with middleware
- Lifecycle management (startup/shutdown hooks)
- YAML configuration with environment overrides
- Plugin architecture

### Time Utilities (`appinfra/time/`)

Comprehensive time-related utilities:
- Monotonic timing and date conversion
- Ticker: periodic task execution
- Scheduler: daily/weekly/monthly/hourly execution
- Delta: duration formatting (4 formats)
- DateRange: memory-efficient iteration

### Network Components (`appinfra/net/`)

TCP/HTTP server infrastructure:
- Single-process and multiprocessing modes
- HTTP request handling with routing
- Graceful shutdown
- Exception handling framework

### Core Utilities

- `DotDict` - Dictionary with attribute-style access and dot-notation path traversal
- `lru_cache` - LRU cache implementation
- `rate_limit` - Operation frequency control
- YAML utilities with include support, type checking helpers

## Installation

```bash
# From PyPI
pip install appinfra

# Or for development
git clone https://github.com/serendip-ml/appinfra.git
cd appinfra
make setup
```

## Quick Start

### Basic Logging

```python
from appinfra.log import LoggingBuilder

logger = (
    LoggingBuilder("my_app")
    .with_level("info")
    .console_handler()
    .file_handler("logs/app.log")
    .build()
)

logger.info("Hello world", extra={"user_id": "123"})
```

### Configuration

```python
from appinfra.app.cfg import Config

config = Config("etc/infra.yaml")
print(config.logging.level)  # Environment vars can override YAML values
```

### Database

```python
from appinfra.db import PG
import sqlalchemy

pg = PG("etc/infra.yaml", "main")
with pg.session() as session:
    result = session.execute(sqlalchemy.text("SELECT 1"))
```

## Project Scaffolding

Quickly generate new projects with the scaffold tool:

```bash
# Generate standalone project (self-contained Makefile)
appinfra scaffold myapp

# Generate framework-based project (includes modular Makefiles)
appinfra scaffold myapp --makefile-style=framework

# With database support
appinfra scaffold myapp --with-db

# With HTTP server
appinfra scaffold myapp --with-server

# With database logging handler
appinfra scaffold myapp --with-logging-db
```

**Makefile Styles:**

- **Standalone** (default): Self-contained Makefile with basic targets (install, test, clean, fmt,
  lint). No framework dependencies.
- **Framework**: Includes modular framework Makefiles with advanced features (test categorization,
  coverage targets, extensibility).

## Configuration

Configuration via `etc/infra.yaml` with environment variable overrides.

### Environment Variables

**Pattern:** `INFRA_<SECTION>_<KEY>`

```bash
# Override logging level
export INFRA_LOGGING_LEVEL=debug

# Override database port
export INFRA_PGSERVER_PORT=5432
```

See [Environment Variables Guide](guides/environment-variables.md) for full documentation.

### Automatic Path Resolution

Config files support automatic resolution of relative paths to absolute paths based on the file
location.

**How it works:**
- Paths starting with `./` or `../` are automatically resolved to absolute paths
- Paths resolve relative to the config file where they're defined
- Works correctly with `!include` - included file paths resolve relative to the included file
- Enabled by default, can be disabled with `resolve_paths=False`

**Example:**

```yaml
# Config at /app/etc/config.yaml
logging:
  file: ./logs/app.log              # Resolves to /app/etc/logs/app.log
  error_file: ../errors/error.log   # Resolves to /app/errors/error.log

database:
  cert_path: ./certs/pg.crt         # Resolves to /app/etc/certs/pg.crt
```

**Usage:**

```python
from appinfra.app.cfg import Config

# Default: path resolution enabled
config = Config('etc/config.yaml')
print(config.logging.file)  # /absolute/path/to/etc/logs/app.log

# Disable path resolution
config = Config('etc/config.yaml', resolve_paths=False)
print(config.logging.file)  # ./logs/app.log
```

## CLI Commands

After installation, the `appinfra` command provides useful utilities:

```bash
appinfra docs              # Show documentation overview
appinfra docs list         # List all available docs and examples
appinfra docs show <topic> # Show specific documentation
appinfra docs find <text>  # Search documentation
appinfra scaffold <name>   # Generate a new project
appinfra config [file]     # Show resolved configuration (aliases: c, cfg)
appinfra cq cf             # Check function sizes
```

## Requirements

- Python 3.11+
- PostgreSQL 17 (optional, for database features)
- Docker (optional, for PostgreSQL in development)

**Core dependencies:**
- SQLAlchemy 2.0+
- PyYAML 6.0+
- psycopg2-binary

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
