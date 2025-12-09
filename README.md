# appinfra

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)
![Type Hints](https://img.shields.io/badge/type%20hints-100%25-brightgreen.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

Production-grade Python infrastructure framework for building reliable CLI tools and services.

## Features

- **Logging** - Structured logging with custom levels, rotation, JSON output, and database handlers
- **Database** - PostgreSQL interface with connection pooling and query monitoring
- **App Framework** - Fluent builder API for CLI tools with lifecycle management
- **Configuration** - YAML config with environment variable overrides and path resolution
- **Time Utilities** - Scheduling, periodic execution, and duration formatting

## Installation

```bash
pip install appinfra
```

## Quick Start

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

## Documentation

Full documentation is available in [docs/README.md](docs/README.md), or via CLI:

```bash
appinfra docs           # Overview
appinfra docs list      # List all guides and examples
appinfra docs show <topic>  # Read a specific guide
```

## Contributing

See the [Contributing Guide](docs/guides/contributing.md) for development setup and guidelines.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
