"""
Tests for configuration schemas and validation.

Tests Pydantic-based validation for configuration schemas including:
- PostgreSQL server configuration validation
- Database configuration validation
- Logging configuration validation
"""

import pytest

try:
    from pydantic import ValidationError

    from appinfra.config.schemas import (
        PYDANTIC_AVAILABLE,
        DatabaseConfig,
        LoggingConfig,
        PostgreSQLServerConfig,
    )

    SKIP_REASON = None
except ImportError:
    SKIP_REASON = "pydantic not installed"
    PYDANTIC_AVAILABLE = False


@pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason=SKIP_REASON or "pydantic not available"
)
@pytest.mark.unit
class TestPostgreSQLServerConfigValidation:
    """Test PostgreSQL server configuration validation."""

    def test_invalid_port_negative(self):
        """Test that negative port raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            PostgreSQLServerConfig(port=-1)

    def test_invalid_port_too_high(self):
        """Test that port > 65535 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 65535"):
            PostgreSQLServerConfig(port=70000)

    def test_valid_port_boundary_values(self):
        """Test that boundary port values are accepted."""
        # Port 1 should be valid
        config1 = PostgreSQLServerConfig(port=1)
        assert config1.port == 1

        # Port 65535 should be valid
        config2 = PostgreSQLServerConfig(port=65535)
        assert config2.port == 65535


@pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason=SKIP_REASON or "pydantic not available"
)
@pytest.mark.unit
class TestDatabaseConfigValidation:
    """Test database configuration validation."""

    def test_invalid_url_no_prefix(self):
        """Test that URL without postgresql:// prefix raises ValidationError."""
        with pytest.raises(ValidationError, match="must start with"):
            DatabaseConfig(url="http://localhost/db")

    def test_invalid_url_wrong_scheme(self):
        """Test that URL with wrong scheme raises ValidationError."""
        with pytest.raises(ValidationError, match="must start with"):
            DatabaseConfig(url="mysql://localhost/db")

    def test_valid_url_postgresql_prefix(self):
        """Test that URL with postgresql:// prefix is valid."""
        config = DatabaseConfig(url="postgresql://localhost/db")
        assert config.url == "postgresql://localhost/db"

    def test_valid_url_postgres_prefix(self):
        """Test that URL with postgres:// prefix is valid."""
        config = DatabaseConfig(url="postgres://user:pass@localhost:5432/db")
        assert config.url == "postgres://user:pass@localhost:5432/db"


@pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason=SKIP_REASON or "pydantic not available"
)
@pytest.mark.unit
class TestLoggingConfigValidation:
    """Test logging configuration validation."""

    def test_invalid_log_level(self):
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid log level"):
            LoggingConfig(level="INVALID_LEVEL")

    def test_invalid_log_level_wrong_case(self):
        """Test that log level with wrong case raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid log level"):
            LoggingConfig(level="invalid")

    def test_valid_log_levels(self):
        """Test that all valid log levels are accepted."""
        valid_levels = [
            "TRACE2",
            "TRACE",
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]
        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_valid_log_level_lowercase(self):
        """Test that lowercase valid log level is accepted (case insensitive)."""
        # The validator converts to uppercase, so lowercase should work
        config = LoggingConfig(level="info")
        assert config.level == "info"
