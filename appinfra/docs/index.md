# appinfra Documentation

## How to Navigate

```bash
appinfra docs                    # Show this index
appinfra docs show README        # Read the full user guide
appinfra docs show <guide-name>  # Read a specific guide (e.g., "logging-builder" or "logging-builder.md")
appinfra docs list               # List all available docs and examples
appinfra docs find <text>        # Search documentation for text
```

## User Guide

- [README](README.md) - Full user documentation, features, configuration

## Guides

- [Logging Builder](guides/logging-builder.md) - Fluent API for logging configuration
- [Config-Based Logging](guides/config-based-logging.md) - YAML-based logging setup
- [Hot-Reload Logging](guides/hot-reload-logging.md) - Dynamic config reloading without restart
- [Environment Variables](guides/environment-variables.md) - Override config with env vars
- [PostgreSQL Test Helper](guides/pg-test-helper.md) - Testing with PostgreSQL
- [Makefile Customization](guides/makefile-customization.md) - Extending framework Makefiles
- [Virtual Environment](guides/virtual-environment.md) - Development environment setup
- [Test Naming Standards](guides/test-naming-standards.md) - Test naming conventions
- [Coverage Targets](guides/coverage-targets.md) - Test coverage guidelines
- [Contributing](guides/contributing.md) - Development setup and guidelines

## API Reference

- [Application Framework](api/app.md) - Core application classes
- [AppBuilder](api/app-builder.md) - Fluent builder API
- [FastAPI Server](api/fastapi.md) - HTTP server with subprocess isolation
- [Logging System](api/logging.md) - Logger and handlers
- [Database Layer](api/database.md) - PostgreSQL interface
- [Time & Scheduling](api/time.md) - Ticker, scheduler, utilities
- [Utilities](api/utilities.md) - DotDict, Config, rate limiting
- [Exceptions](api/exceptions.md) - Exception hierarchy

## Examples

- [01_basics](../examples/01_basics/) - Basic usage patterns
- [02_app_framework](../examples/02_app_framework/) - Application framework
- [03_logging](../examples/03_logging/) - Logging examples
- [04_configuration](../examples/04_configuration/) - Configuration patterns
- [05_database](../examples/05_database/) - Database usage
- [06_advanced](../examples/06_advanced/) - Advanced patterns
- [08_decorators](../examples/08_decorators/) - Decorator-based tool definitions

## Other

- [LICENSE](LICENSE) - Apache License 2.0
- [SECURITY](SECURITY.md) - Security policy
