# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For API stability guarantees and deprecation policy, see
[API Stability Policy](appinfra/docs/guides/api-stability.md).

## [Unreleased]

### Added
- Standard CLI arguments for agent-friendly log output:
  - `--log-json` - Output logs in JSON format (overrides YAML handler `format: text`)
  - `--no-log-colors` - Disable colored log output (overrides YAML handler `colors: true`)
  - Both flags apply to all console handlers defined in config, not just the first one
  - Available by default; disable with `.with_standard_args(log_json=False, log_colors=False)`
- `ConsoleHandlerConfig.colors` parameter for handler-specific color control. When set, overrides
  the global `LogConfig.colors` setting for that specific handler.
- Configuration precedence guide (`docs/guides/configuration-precedence.md`) documenting the full
  override hierarchy: CLI args > Environment variables > YAML config > Defaults. Also covers
  topic-level priorities (API=10, CLI=5, YAML=1) and handler override behavior.
- Docstring coverage checking via `interrogate`:
  - `make cq.docstring` - Report docstring coverage without failing
  - `make cq.docstring.strict` - Fail if below threshold
  - Integrated into `make check` with percentage display (e.g., `95.30% ≥ 95%`)
  - Configurable via `INFRA_DEV_DOCSTRING_THRESHOLD` (default: 80, set to 0 to disable)

### Changed
- `DotDict.__init__()` now accepts dict as positional argument, matching built-in `dict()` API:
  - `DotDict({"a": 1, "b": 2})` now works alongside existing `DotDict(a=1, b=2)`
  - Kwargs override positional dict values when both are provided
  - Backward compatible - existing code using only kwargs continues to work
- Default coverage threshold lowered from 95% to 80% (`INFRA_PYTEST_COVERAGE_THRESHOLD`)
  - Projects can override to higher thresholds as needed
  - appinfra itself still uses 95% for both test and docstring coverage

### Fixed
- Environment variable overrides with hyphenated YAML keys now handle edge cases correctly:
  - Fixed `AttributeError` crash when env vars target non-dict YAML values (scalars, lists, null)
  - Fixed ambiguous key matching - `INFRA_SERVICES_WEB_SERVER_PORT` now correctly prioritizes
    exact matches (`web_server`) over shorter matches (`web`)
  - Scalar and null values are now replaced with dicts when env vars create nested paths
  - List values remain unchanged when env vars attempt nested overrides (cannot traverse into lists)
  - Added comprehensive test coverage (23 new tests) for edge cases and backward compatibility
- Coverage display formatting now consistent across all projects:
  - Both actual and target percentages show 1 decimal place (e.g., `89.9% ≥ 90.0%`)
  - Uses pessimistic floor rounding to prevent misleading displays (89.99% shows as 89.9%, not 90.0%)
  - Previously varied between 0-2 decimals depending on pytest output

## [0.3.4] - 2026-02-03

### Added
- Documentation for merge policy and release process in contributing guide
- Multiprocess logging support (`appinfra.log.mp`) for child processes:
  - **Queue mode**: `MPQueueHandler` in subprocesses sends records to parent via `LogQueueListener`
  - **Independent mode**: `LoggingBuilder.to_dict()`/`from_dict()` for self-sufficient subprocess logging
  - `Logger.with_queue(queue, name)` convenience method for subprocess queue handlers
  - Automatic exception formatting before pickling (traceback preserved across processes)
  - Database handlers are excluded from serialization (not supported in multiprocess mode)
- Simplified queue config API for multiprocess logging:
  - `Logger.queue_config(queue)` - Creates a picklable config dict containing queue, level, and
    `LogLevelManager` rules. One call captures everything workers need.
  - `Logger.from_queue_config(config, name)` - Creates a subprocess logger from the config. Pattern-based
    level rules are restored and applied based on the logger name.
  - `LogLevelManager.to_dict()` / `from_dict()` - Serialize and restore topic-based level rules for
    multiprocess scenarios
- `ErrorContext` and `IncludeContext` dataclasses in `appinfra.yaml` for error location tracking

### Changed
- Refactored `appinfra.yaml` from single module to package for better maintainability.
  Public API unchanged - all existing imports (`load`, `Loader`, `deep_merge`, `ErrorContext`,
  `IncludeContext`, `SecretLiteralWarning`) continue to work.

### Fixed
- Examples now work when run from the repository. Path setup was incorrect (`parents[2]` instead
  of `parents[3]`), causing the local `yaml/` module to shadow PyYAML. Also added missing path
  setup to 3 examples and removed stale `02a_app_using_framework` directory.
- YAML `!include` directive errors now logged with file location instead of failing silently.
  Previously, when `AppBuilder.with_config_file()` loaded a config with a bad `!include`
  (missing file, circular include, etc.), the error was silently swallowed, resulting in empty
  config sections with no indication of what went wrong. Now errors are stored during config
  loading and logged with file path, line number, and column once the logger is initialized.
- Variable interpolation in section includes (`!include './file.yaml#section'`) now works
  correctly. Previously, `${sibling.key}` references to other sections in the same source file
  would fail because section extraction happened before variable resolution. Now variables are
  resolved within the full file context before extracting the section.

## [0.3.3] - 2026-01-29

### Added
- PostgreSQL schema isolation for parallel test execution and multi-tenant applications. Each `PG`
  instance can use a dedicated schema (e.g., `test_gw0`, `test_gw1`) to isolate data. Useful for
  running tests with pytest-xdist without race conditions.
  - `PG(logger, config, schema="my_schema")` - Initialize with schema isolation
  - `pg.schema` property - Get configured schema name
  - `pg.create_schema()` - Create the schema if it doesn't exist
  - Tables are created in the schema during `pg.migrate()`
  - Queries are routed via `search_path` (includes `public` for extension visibility)
- `SchemaManager` class for direct schema management (`appinfra.db.pg.SchemaManager`)
- Pytest fixtures module for schema-isolated testing (`appinfra.db.pg.testing`):
  - `pg_test_schema` - Generates unique schema name per pytest-xdist worker
  - `pg_isolated` - Session-scoped PG with schema isolation
  - `pg_session_isolated` - Per-test session with auto commit/rollback
  - `pg_clean_schema` - Fresh schema for each test
  - `pg_migrate_factory` - Context manager factory for PG with migrations (recommended)
  - `make_migrate_fixture(Base)` - Legacy factory for migration fixtures
- `schema` field in database config for declarative schema isolation

### Fixed
- `make check` fail-fast now immediately kills remaining background jobs when a check fails.
  Previously, fail-fast only stopped waiting for results while other checks (especially tests)
  continued running in the background until script exit.
- `PytestAssertRewriteWarning` when using `appinfra.db.pg.testing` with `make_migrate_fixture`.
  The new `pg_migrate_factory` fixture avoids the warning by not requiring imports from the module.

## [0.3.2] - 2026-01-25

### Added
- PEP 561 `py.typed` marker file for type checker support. Downstream packages can now use appinfra's
  type annotations with mypy/pyright without `--ignore-missing-imports`.
- Documentation for argparse positional argument ordering limitation in `app.md`
- `INFRA_DEV_MYPY_FLAGS` variable for passing extra flags to mypy (e.g., `--follow-imports=skip`
  for projects with large dependencies like torch/transformers that cause mypy to hang)
- `INFRA_DEV_SKIP_TARGETS` variable to skip built-in targets (`fmt`, `lint`, `type`, `cq`) so
  projects can provide their own implementations (e.g., custom mypy flags per directory)

### Changed
- `Tool.lg` property now returns `Logger` instead of `Logger | None`. Raises `MissingLoggerError`
  if accessed before `setup()`. This eliminates the need for defensive `if self.lg:` checks or
  `assert self.lg is not None` in tool code. The logger is always available after `setup()` runs.

### Fixed
- `check.sh` now runs E2E and Performance tests sequentially using `-n 0` instead of `-n 1`.
  Previously, `-n 1` still used pytest-xdist with a single worker, which behaves differently than
  true sequential execution.
- `check.sh` now respects `PYTEST_PARALLEL` for E2E and Performance test commands, allowing parallel
  execution when explicitly enabled.

## [0.3.1] - 2026-01-20

### Added
- Lifecycle callback support for FastAPI ServerBuilder:
  - `with_on_startup(callback)` - Run async callbacks when app starts
  - `with_on_shutdown(callback)` - Run async callbacks when app shuts down (continues on errors)
  - `with_lifespan(context_manager)` - Use FastAPI's modern lifespan pattern
  - `with_on_request(callback)` - Run callbacks before each request (after custom middleware)
  - `with_on_response(callback)` - Run callbacks after each request (can modify response)
  - `with_on_exception(callback)` - Run callbacks on unhandled exceptions
- Request/response callbacks run inside custom middleware, allowing access to auth state and other
  middleware-injected context
- Startup callback failures now include callback name in error message for easier debugging
- Shutdown callbacks continue executing even if earlier callbacks fail (errors are logged)
- `INFRA_DEV_CQ_EXCLUDE` variable for excluding directories from function size checks. Set glob
  patterns (e.g., `INFRA_DEV_CQ_EXCLUDE := examples/* scripts/*`) to skip specified paths in both
  `make cq` and `make check`.

### Fixed
- `with_on_startup()` no longer breaks IPC response queue in subprocess mode. Previously, using
  lifecycle callbacks with `.subprocess.with_ipc()` caused responses to never be delivered because
  FastAPI ignores `on_event()` handlers when a lifespan is present. IPC polling is now integrated
  directly into the adapter's lifespan context manager.
- `with_main_tool()` no longer causes positional argument conflicts with subcommands. Previously,
  main tool positional args were hoisted to the root parser, consuming arguments before the
  subcommand name could be recognized (e.g., `./app query "file"` would fail because `"query"` was
  consumed by the main tool's positional arg). Now only optional arguments are hoisted.
- YAML merge keys (`<<: *anchor`) now work correctly when source tracking is enabled. Previously,
  Config class would fail with `ConstructorError` when loading YAML files using anchors and merge
  keys.

## [0.3.0] - 2026-01-15

### Added
- Custom Docker image support for PostgreSQL server via `pgserver.image` config field. Enables using
extension images like `pgvector/pgvector:pg16` or `timescale/timescaledb:latest-pg16`. When `image`
is specified, `version` becomes optional. The image must be PostgreSQL-compatible (based on official
  `postgres` image) as docker-compose passes postgres-specific CLI arguments.
- PostgreSQL server configuration via `pgserver.postgres_conf` dict for passing `-c key=value`
  parameters to postgres. Supports strings, integers, booleans (converted to on/off), and lists
  (joined with commas for `shared_preload_libraries` etc.).
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
- `DotDict` now correctly prioritizes data over inherited dict methods. Previously, keys like
  `copy`, `pop`, or `update` would return the dict method instead of the stored value.

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

[Unreleased]: https://github.com/serendip-ml/appinfra/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/serendip-ml/appinfra/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/serendip-ml/appinfra/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/serendip-ml/appinfra/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/serendip-ml/appinfra/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/serendip-ml/appinfra/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/serendip-ml/appinfra/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/serendip-ml/appinfra/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/serendip-ml/appinfra/releases/tag/v0.1.0
