# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For API stability guarantees and deprecation policy, see
[API Stability Policy](docs/guides/api-stability.md).

## [Unreleased]

### Fixed
- LICENSE now displays properly on GitHub (converted from symlink to real file)
- `appinfra docs show LICENSE` command now works correctly
- Removed obsolete symlink resolution step from release workflow

### Changed
- Removed SECURITY.md symlink from repository root (still available via `appinfra docs`)

## [0.1.2] - 2026-01-05

### Fixed
- Wheel builds now work correctly (reversed symlink direction: real files in `appinfra/`, symlinks at root)
- Duplicate CI checks on develop branch PRs
- Docker build context and paths for new project structure
- Coverage job configuration (postgres service, cleanup, output paths)

### Changed
- Restructured CI workflow: lint gate runs first, then parallel test matrix
- Shortened workflow and job names for cleaner GitHub UI
- Consolidated coverage output under `.coverage/` directory
- Aligned `make cicd.test` with GitHub CI workflow

## [0.1.1] - 2026-01-03

### Added
- README as PyPI project description

### Changed
- Lowered performance test threshold for CI environments

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

[Unreleased]: https://github.com/serendip-ml/appinfra/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/serendip-ml/appinfra/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/serendip-ml/appinfra/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/serendip-ml/appinfra/releases/tag/v0.1.0
