# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For API stability guarantees and deprecation policy, see
[API Stability Policy](docs/guides/api-stability.md).

## [Unreleased]

### Added
- API stability policy documentation (`docs/guides/api-stability.md`)
- Output abstraction for testable CLI tools (`appinfra.cli.output`)
- FastAPI integration module with subprocess isolation and IPC

### Changed
- Improved FastAPI optional dependency handling with cleaner stub classes

## [0.1.0] - 2026-01-02

### Added
- Advanced logging system with structured output, custom levels (TRACE/TRACE2), and multiple handlers
- PostgreSQL database layer with connection pooling, query logging, and migration support
- Application framework with fluent AppBuilder API, tool registry, and lifecycle management
- Time utilities: Ticker (periodic execution), Scheduler (cron-like), Delta (duration formatting), DateRange
- Network components: TCP/HTTP server with single-process and multiprocessing modes
- Core utilities: DotDict, LRU cache, rate limiting, YAML configuration with environment overrides
- Comprehensive test suite with 95% coverage across unit, integration, performance, security, and e2e tests
- Documentation for all major components and configuration patterns
- Security best practices and vulnerability reporting policy

### Changed
- Package renamed to `appinfra` (install and import both use `appinfra`)

[0.1.0]: https://github.com/serendip-ml/appinfra/releases/tag/v0.1.0
