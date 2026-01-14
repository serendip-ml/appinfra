# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For API stability guarantees and deprecation policy, see
[API Stability Policy](appinfra/docs/guides/api-stability.md).

## [Unreleased]

### Added
- Custom Docker image support for PostgreSQL server via `pgserver.image` config field. Enables using
extension images like `pgvector/pgvector:pg16` or `timescale/timescaledb:latest-pg16`. When `image`
is specified, `version` becomes optional. The image must be PostgreSQL-compatible (based on official
  `postgres` image) as docker-compose passes postgres-specific CLI arguments.
- PostgreSQL server configuration via `pgserver.postgres_conf` dict for passing `-c key=value`
  parameters to postgres. Supports strings, integers, booleans (converted to on/off), and lists
  (joined with commas for `shared_preload_libraries` etc.).
- PostgreSQL config file support via `pgserver.postgres_conf_file` for loading a full
  `postgresql.conf`. When both are specified, `postgres_conf` values override the config file.
- Declarative PostgreSQL extension support via `dbs.<name>.extensions` list. Extensions are created
  with `CREATE EXTENSION IF NOT EXISTS` during `PG.migrate()`. Extension names are validated to
  prevent SQL injection.
- Lifecycle hooks for PG class: `pg.on_before_migrate(callback)` and `pg.on_after_migrate(callback)`
  for custom setup/teardown during migrations. Callbacks receive a SQLAlchemy connection object.

### Changed
- Removed hardcoded PostgreSQL parameters from docker-compose files. Server now starts with
  PostgreSQL defaults unless `postgres_conf` is specified. Recommended settings are documented.

### Fixed
- `appinfra.db.pg.PG` now accepts dict configs by normalizing them to `SimpleNamespace` at
  initialization. Previously, dict configs would silently fail because `getattr()` on a dict returns
  the default value instead of the dict key value.

## [0.2.1] - 2026-01-11

### Fixed
- `appinfra.db.pg` now uses consistent attribute access pattern (`getattr`) throughout instead of
  dict-style `.get()`. This allows using SimpleNamespace, dataclasses, or any object with attributes
as config. Affected: `ConfigValidator`, `PG.readonly`, `PG.migrate()`,
`ConnectionManager.connect()`.

## [0.2.0] - 2026-01-11

### Added
- API documentation for CLI framework (`cli.md`), configuration (`config.md`), network (`net.md`),
  observability (`observability.md`), security (`security.md`), and subprocess (`subprocess.md`)
- Configurable coverage threshold via `INFRA_PYTEST_COVERAGE_THRESHOLD` (default: 95.0, set to 0 to disable)
- SQLite database support (`appinfra.db.sqlite`) for lightweight/embedded use cases
- pgvector extension support (`appinfra.db.pg.vector`) for embedding storage and similarity search
- SQLite integration fixtures for fast DB tests (no external server needed)
- Session-start cleanup for stale debug tables (prevents orphaned tables from accumulating)
- Session detachment utilities (`appinfra.db.utils`) for background processing
- Test for debug table retention-on-failure behavior
- YAML frontmatter support for `appinfra docs search` - docs can include searchable keywords/aliases
- Fuzzy matching for `appinfra docs search` via `--fuzzy` flag with configurable `--threshold`
- Root-level SECURITY.md symlink for GitHub security integration discoverability
- CodeRabbit AI code review integration (`.coderabbit.yaml`) for automated PR reviews
- CODEOWNERS file requiring @serendip-ml approval for all changes

### Changed
- Restructure `docs/README.md` as focused user guide with Architecture and Packages sections
- Default PostgreSQL version changed from 17 to 16 (psql client compatibility issues with PG17)
- Database names standardized to `infra_main` and `infra_test` to avoid global name conflicts
- Replace `exec()` with `importlib.util` in version/info.py for safer module loading

### Removed
- **BREAKING:** Remove automatic path resolution from `Config` class. The `resolve_paths` parameter
  has been removed. Path resolution now requires the explicit `!path` YAML tag. This provides a
  cleaner mental model: without `!path`, paths remain as literal strings; with `!path`, paths are
  resolved relative to the config file and tilde (`~`) is expanded. Migration: add `!path` tag to
  config values that need path resolution (e.g., `file: !path ./logs/app.log`).

### Fixed
- Fix flaky integration tests with pytest-xdist by skipping stale table cleanup on worker processes
- Fix documentation links to use actual paths instead of symlinks (GitHub doesn't follow symlinks)
- Suppress passlib `crypt` module deprecation warning (upstream issue, Python 3.13 compatibility)
- Coverage directory handling in Makefile (properly cleans existing .coverage file/directory)

## [0.1.3] - 2026-01-05

### Added
- `DotDict.require()` method - raises `DotDictPathNotFoundError` if path not found

### Changed
- `DotDict` now subclasses `dict` - `isinstance(dotdict, dict)` returns `True`
- Removed SECURITY.md symlink from repository root (still available via `appinfra docs`)

### Fixed
- LICENSE now displays properly on GitHub (converted from symlink to real file)
- `appinfra docs show LICENSE` command now works correctly
- Removed obsolete symlink resolution step from release workflow
- CONTRIBUTING.md symlink now points directly to `appinfra/docs/` for single-click navigation

### Documentation
- Added missing `select_table` parameters (`default_index`, `column_spacing`) to UI docs
- Added shared arguments pattern for tool hierarchies (base class and mixin patterns)

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

[Unreleased]: https://github.com/serendip-ml/appinfra/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/serendip-ml/appinfra/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/serendip-ml/appinfra/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/serendip-ml/appinfra/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/serendip-ml/appinfra/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/serendip-ml/appinfra/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/serendip-ml/appinfra/releases/tag/v0.1.0
