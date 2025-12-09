"""
PostgreSQL database interface implementation.

Provides a complete PostgreSQL database interface with SQLAlchemy integration,
using composition pattern for clean separation of concerns.
"""

from typing import Any

import sqlalchemy
import sqlalchemy_utils

from ...log import LoggerFactory
from .connection import ConnectionManager
from .core import (
    ConfigValidator,
    QueryLogger,
    configure_readonly_mode,
    initialize_connection_health,
    initialize_logging_context,
    initialize_performance_optimizations,
    validate_init_params,
)
from .interface import Interface
from .reconnection import ReconnectionStrategy
from .session import SessionManager


class PG(Interface):
    """
    PostgreSQL database interface implementation.

    Provides a complete PostgreSQL database interface with SQLAlchemy integration,
    including connection management, query logging, migration support, and
    read-only connection capabilities.

    Uses composition pattern with specialized manager classes for clean
    separation of concerns.

    Example:
        >>> from appinfra.db.pg import PG
        >>> from appinfra.log import LoggerFactory, LogConfig
        >>>
        >>> # Create logger and config
        >>> log_config = LogConfig.from_params(level="info")
        >>> logger = LoggerFactory.create_root(log_config)
        >>> db_config = {"url": "postgresql://user:pass@localhost/mydb"}
        >>>
        >>> # Initialize and use
        >>> pg = PG(logger, db_config)
        >>> with pg.session() as session:
        ...     result = session.execute("SELECT 1")
    """

    # Type annotations for instance attributes
    _dialect: Any
    _cached_regex: Any
    _whitespace_regex: Any
    _lg_extra: dict[str, Any]
    _query_lg_level: int | bool | None
    _auto_reconnect: bool
    _max_retries: int
    _retry_delay: float
    # Event listener attributes (set conditionally)
    _readonly_listener: Any
    _after_execute_listener: Any
    _before_cursor_listener: Any

    def __init__(self, lg: Any, cfg: Any, query_lg_level: Any | None = None) -> None:
        """
        Initialize the PostgreSQL database interface.

        Args:
            lg: Logger instance for database operations
            cfg: Database configuration object
            query_lg_level: Log level for query logging (optional)
        """
        validate_init_params(lg, cfg)

        self._cfg = cfg
        self._lg = LoggerFactory.derive(lg, "pg")

        # Validate and create engine
        ConfigValidator.validate_config(cfg)
        self._create_engine_and_session(cfg)

        # Initialize subsystems
        self._initialize_subsystems(query_lg_level)

        # Create and connect managers
        self._create_managers()
        self._setup_query_logging(query_lg_level)

    def _create_engine_and_session(self, cfg: Any) -> None:
        """Create SQLAlchemy engine and session maker."""
        engine_kwargs = ConfigValidator.get_engine_kwargs(cfg)
        self._engine = sqlalchemy.create_engine(self._cfg.url, **engine_kwargs)
        self._SessionCls = sqlalchemy.orm.sessionmaker(bind=self._engine)

    def _initialize_subsystems(self, query_lg_level: Any) -> None:
        """Initialize configuration and tracking subsystems."""
        configure_readonly_mode(self)
        initialize_logging_context(self, query_lg_level)
        initialize_performance_optimizations(self)
        initialize_connection_health(self)

    def _create_managers(self) -> None:
        """Create manager instances and connect them."""
        self._connection_mgr = ConnectionManager(
            self._engine, self._lg, self._cfg, self.readonly
        )
        self._session_mgr = SessionManager(
            self._SessionCls, self._lg, self._auto_reconnect
        )
        self._reconnect_strategy = ReconnectionStrategy(
            self._engine, self._lg, self._max_retries, self._retry_delay
        )
        self._query_logger = QueryLogger(self._engine, self._lg, self._query_lg_level)

        # Connect managers
        self._session_mgr.set_reconnect_strategy(self._reconnect_strategy)
        self._update_logging_context()

    def _setup_query_logging(self, query_lg_level: Any) -> None:
        """Setup query logging callbacks if enabled."""
        if query_lg_level is not None:
            self._query_logger.setup_callbacks(self._lg_extra)

    def _update_logging_context(self) -> None:
        """Update logging context on all managers."""
        self._connection_mgr.set_logging_context(self._lg_extra)
        self._session_mgr.set_logging_context(self._lg_extra)
        self._reconnect_strategy.set_logging_context(self._lg_extra)

    @property
    def cfg(self) -> Any:
        """Get the database configuration."""
        return self._cfg

    @property
    def url(self) -> str:
        """Get the database URL."""
        return str(self._engine.url)

    @property
    def readonly(self) -> bool:
        """Check if connection is read-only."""
        return self._cfg.get("readonly", False) is True

    @property
    def engine(self) -> sqlalchemy.engine.Engine:
        """Get the SQLAlchemy engine."""
        return self._engine

    def connect(self) -> Any:
        """
        Establish a connection to the PostgreSQL database.

        Returns:
            Database connection object

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If connection fails

        Example:
            >>> pg = PG(logger, config)
            >>> conn = pg.connect()
            >>> result = conn.execute(sqlalchemy.text("SELECT version()"))
            >>> print(result.fetchone()[0])
            PostgreSQL 15.4 ...
            >>> conn.close()
        """
        return self._connection_mgr.connect()

    def migrate(self, base: Any) -> None:  # type: ignore[override]
        """
        Run database migrations using SQLAlchemy metadata.

        Creates all tables defined in the metadata if they don't exist.

        Args:
            base: SQLAlchemy declarative base with metadata

        Example:
            >>> from sqlalchemy.orm import declarative_base
            >>> from sqlalchemy import Column, Integer, String
            >>>
            >>> Base = declarative_base()
            >>>
            >>> class User(Base):
            ...     __tablename__ = "users"
            ...     id = Column(Integer, primary_key=True)
            ...     name = Column(String(100))
            >>>
            >>> pg = PG(logger, config)
            >>> pg.migrate(Base)  # Creates 'users' table if not exists
        """
        # Ensure database exists if create_db is enabled
        create_db = self._cfg.get("create_db", False)
        if create_db is True and not sqlalchemy_utils.database_exists(self._engine.url):
            sqlalchemy_utils.create_database(self._engine.url)
            self._lg.info("created db", extra=self._lg_extra)

        base.metadata.create_all(self._engine)

    def session(self) -> Any:
        """
        Create a new database session with automatic reconnection if enabled.

        Returns:
            Database session instance

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If session creation fails

        Example:
            >>> pg = PG(logger, config)
            >>> session = pg.session()
            >>> try:
            ...     result = session.execute(sqlalchemy.text("SELECT * FROM users"))
            ...     users = result.fetchall()
            ...     session.commit()
            ... except Exception:
            ...     session.rollback()
            ...     raise
            ... finally:
            ...     session.close()
        """
        # Update session manager's health status
        self._session_mgr.set_connection_health(self._reconnect_strategy.is_healthy())
        return self._session_mgr.session()

    def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the database connection.

        Returns:
            Dictionary with health check results
        """
        return self._connection_mgr.health_check()

    def get_pool_status(self) -> dict[str, Any]:
        """
        Get connection pool status information.

        Returns:
            Dictionary with pool status
        """
        return self._connection_mgr.get_pool_status()

    def reconnect(
        self, max_retries: int | None = None, initial_delay: float | None = None
    ) -> bool:
        """
        Reconnect to the database with exponential backoff.

        Args:
            max_retries: Maximum retry attempts (uses default if None)
            initial_delay: Initial retry delay (uses default if None)

        Returns:
            True if reconnection successful

        Raises:
            DatabaseError: If reconnection fails after all retries
        """
        result = self._reconnect_strategy.reconnect(max_retries, initial_delay)
        # Update session manager's health status
        self._session_mgr.set_connection_health(self._reconnect_strategy.is_healthy())
        return result
