"""Tests for appinfra.db.pg.pg error handling and edge cases."""

from unittest.mock import Mock

import pytest

from appinfra.db.pg.connection import validate_readonly_config
from appinfra.db.pg.core import validate_init_params


@pytest.mark.unit
class TestPGValidation:
    """Test PG class input validation."""

    def testvalidate_init_params_rejects_none_logger(self):
        """Test that validate_init_params raises ValueError for None logger."""
        mock_cfg = Mock()

        with pytest.raises(ValueError) as exc_info:
            validate_init_params(None, mock_cfg)

        assert "Logger cannot be None" in str(exc_info.value)

    def testvalidate_init_params_rejects_none_config(self):
        """Test that validate_init_params raises ValueError for None config."""
        mock_logger = Mock()

        with pytest.raises(ValueError) as exc_info:
            validate_init_params(mock_logger, None)

        assert "Configuration cannot be None" in str(exc_info.value)

    def testvalidate_init_params_accepts_valid_inputs(self):
        """Test that validate_init_params accepts valid inputs."""
        mock_logger = Mock()
        mock_cfg = Mock()

        # Should not raise any exception
        validate_init_params(mock_logger, mock_cfg)

    def testvalidate_readonly_config_rejects_create_db_in_readonly(self):
        """Test that validate_readonly_config raises ValueError for create_db in readonly mode."""
        with pytest.raises(ValueError) as exc_info:
            validate_readonly_config(readonly=True, create_db=True)

        assert "Cannot create database in readonly mode" in str(exc_info.value)

    def testvalidate_readonly_config_accepts_valid_combinations(self):
        """Test that validate_readonly_config accepts valid combinations."""
        # Should not raise any exception
        validate_readonly_config(readonly=False, create_db=True)
        validate_readonly_config(readonly=False, create_db=False)
        validate_readonly_config(readonly=True, create_db=False)


@pytest.mark.unit
class TestPGHelperFunctions:
    """Test PG helper functions."""

    def testcreate_sqlalchemy_engine_with_nullpool(self):
        """Test that create_sqlalchemy_engine creates engine with NullPool."""
        import sqlalchemy

        from appinfra.db.pg.core import create_sqlalchemy_engine

        # Create an in-memory SQLite engine for testing
        engine = create_sqlalchemy_engine("sqlite:///:memory:")

        # Verify it's an engine
        assert isinstance(engine, sqlalchemy.engine.Engine)

        # Verify NullPool is used
        assert isinstance(engine.pool, sqlalchemy.pool.NullPool)

    def testinitialize_performance_cache(self):
        """Test that initialize_performance_cache sets dialect and regex."""
        import re

        import sqlalchemy

        from appinfra.db.pg.core import initialize_performance_cache

        # Create a mock PG instance
        mock_pg = Mock()
        mock_engine = sqlalchemy.create_engine("sqlite:///:memory:")
        mock_pg._engine = mock_engine

        # Initialize cache
        initialize_performance_cache(mock_pg)

        # Verify dialect was cached
        assert mock_pg._dialect == mock_engine.dialect

        # Verify regex was cached
        assert hasattr(mock_pg, "_cached_regex")
        assert isinstance(mock_pg._cached_regex, re.Pattern)

    def testcreate_engine_and_session(self):
        """Test that create_engine_and_session creates engine and session."""
        import sqlalchemy

        from appinfra.db.pg.core import create_engine_and_session

        # Create mock config
        mock_cfg = Mock()
        mock_cfg.url = "sqlite:///:memory:"

        # Create engine and session
        engine, session_cls = create_engine_and_session(mock_cfg)

        # Verify engine was created
        assert isinstance(engine, sqlalchemy.engine.Engine)

        # Verify NullPool was used
        assert isinstance(engine.pool, sqlalchemy.pool.NullPool)

        # Verify session maker was created
        assert callable(session_cls)


@pytest.mark.unit
class TestPGErrorHandlers:
    """Test PG error handling functions."""

    def testlog_query_with_timing_normal_case(self):
        """Test log_query_with_timing in normal case."""
        from appinfra.db.pg.core import log_query_with_timing

        # Create mock logger
        mock_logger = Mock()
        mock_logger.isEnabledFor = Mock(return_value=True)
        mock_logger._log = Mock()

        # Call function
        log_query_with_timing(
            mock_logger, 10, 0.5, "SELECT 1", "postgresql://localhost"
        )

        # Verify logging was called
        mock_logger.isEnabledFor.assert_called_once_with(10)
        mock_logger._log.assert_called_once()

    def testlog_query_with_timing_exception_fallback(self):
        """Test log_query_with_timing fallback to stderr on exception (lines 125-131)."""
        import sys
        from io import StringIO

        from appinfra.db.pg.core import log_query_with_timing

        # Create mock logger that raises exception
        mock_logger = Mock()
        mock_logger.isEnabledFor = Mock(side_effect=Exception("Logger error"))

        # Capture stderr
        captured_stderr = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_stderr

        try:
            # Call function - should catch exception and write to stderr
            log_query_with_timing(
                mock_logger, 10, 0.5, "SELECT 1", "postgresql://localhost"
            )

            # Verify stderr was written
            stderr_output = captured_stderr.getvalue()
            assert "UNABLE TO LOG" in stderr_output
            assert "Logger error" in stderr_output

        finally:
            sys.stderr = old_stderr

    def testhandle_sqlalchemy_error_logs_and_raises(self):
        """Test handle_sqlalchemy_error logs error and re-raises."""
        from appinfra.db.pg.connection import handle_sqlalchemy_error

        # Create mocks
        mock_logger = Mock()
        lg_extra = {"url": "postgresql://localhost"}
        error = Exception("Connection failed")

        # Call function within exception context - should re-raise
        with pytest.raises(Exception) as exc_info:
            try:
                raise error
            except Exception as e:
                handle_sqlalchemy_error(mock_logger, lg_extra, e, 0.0)

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "failed to connect to db" in call_args[0]

        # Verify original exception was raised
        assert exc_info.value is error

    def testhandle_general_error_logs_and_wraps(self):
        """Test handle_general_error logs and wraps in SQLAlchemyError."""
        import sqlalchemy.exc

        from appinfra.db.pg.connection import handle_general_error

        # Create mocks
        mock_logger = Mock()
        lg_extra = {"url": "postgresql://localhost"}
        error = ValueError("Unexpected error")

        # Call function - should wrap and raise
        with pytest.raises(sqlalchemy.exc.SQLAlchemyError) as exc_info:
            handle_general_error(mock_logger, lg_extra, error, 0.0)

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "unexpected error connecting to db" in call_args[0]

        # Verify exception was wrapped
        assert "Database connection failed" in str(exc_info.value)
        assert exc_info.value.__cause__ is error
