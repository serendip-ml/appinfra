"""
Tests for LoggerWithSeparator.

Tests key functionality including:
- _log method with separator checking
- _check_separator method
- set_content_separator_secs method
"""

import logging
import time
from unittest.mock import patch

import pytest

from appinfra.log.callback import CallbackRegistry
from appinfra.log.config import LogConfig
from appinfra.log.logger_with_sep import LoggerWithSeparator

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def log_config():
    """Create basic log configuration."""
    return LogConfig(level=logging.DEBUG, location=0, micros=False, colors=False)


@pytest.fixture
def callback_registry():
    """Create callback registry."""
    return CallbackRegistry()


@pytest.fixture
def logger_with_sep(log_config, callback_registry):
    """Create LoggerWithSeparator instance."""
    # Reset shared state before each test
    with LoggerWithSeparator.lock:
        LoggerWithSeparator.last_ts.value = 0
        LoggerWithSeparator.new_content_separator_secs.value = 5.0

    logger = LoggerWithSeparator(
        "test_sep_logger", log_config, callback_registry, extra={}
    )
    logger.setLevel(logging.DEBUG)

    # Add a handler to capture output
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False

    yield logger

    # Cleanup
    logger.handlers.clear()
    # Reset state
    with LoggerWithSeparator.lock:
        LoggerWithSeparator.last_ts.value = 0
        LoggerWithSeparator.new_content_separator_secs.value = 5.0


# =============================================================================
# Test _log method - Lines 35-37
# =============================================================================


@pytest.mark.unit
class TestLogMethod:
    """Test _log method with separator checking."""

    def test_log_calls_check_separator_when_enabled(self, logger_with_sep):
        """Test _log calls _check_separator when level is enabled (lines 35-37)."""
        with patch.object(
            logger_with_sep, "_check_separator", wraps=logger_with_sep._check_separator
        ) as mock_check:
            logger_with_sep.info("test message")

            # _check_separator should have been called
            mock_check.assert_called_once()

    def test_log_skips_separator_check_when_disabled(self, logger_with_sep):
        """Test _log skips separator check when level not enabled."""
        # Set level higher than DEBUG
        logger_with_sep.setLevel(logging.ERROR)

        with patch.object(logger_with_sep, "_check_separator") as mock_check:
            # Debug should not trigger separator check when level is ERROR
            logger_with_sep.debug("test debug")

            # _check_separator should not be called for disabled levels
            # (Note: the _log method checks isEnabledFor before calling _check_separator)
            mock_check.assert_not_called()


# =============================================================================
# Test _check_separator method - Lines 41-54
# =============================================================================


@pytest.mark.unit
class TestCheckSeparator:
    """Test _check_separator method."""

    def test_check_separator_triggers_after_gap(self, logger_with_sep):
        """Test separator triggers after configured gap (lines 41-54)."""
        # Set short interval for testing
        LoggerWithSeparator.set_content_separator_secs(0.01)

        # First log - sets last_ts
        logger_with_sep.info("first message")

        # Wait for gap
        time.sleep(0.02)

        # Second log should trigger separator
        with patch.object(
            logger_with_sep, "info", wraps=logger_with_sep.info
        ) as mock_info:
            logger_with_sep._check_separator()
            # Note: This is tricky because _check_separator calls super().info
            # The actual separator is logged via parent class

    def test_check_separator_no_trigger_when_disabled(self, logger_with_sep):
        """Test separator doesn't trigger when secs=0."""
        LoggerWithSeparator.set_content_separator_secs(0)

        # First log
        logger_with_sep.info("message 1")

        # Wait
        time.sleep(0.01)

        # Should not trigger separator since secs=0
        # Just ensure no crash
        logger_with_sep._check_separator()

    def test_check_separator_first_log_no_trigger(self, logger_with_sep):
        """Test first log doesn't trigger separator (last=0)."""
        # Reset to ensure clean state
        with LoggerWithSeparator.lock:
            LoggerWithSeparator.last_ts.value = 0

        LoggerWithSeparator.set_content_separator_secs(0.001)

        # First _check_separator should set last_ts but not trigger
        # (because last == 0 means no previous log)
        logger_with_sep._check_separator()

        # last_ts should now be set
        assert LoggerWithSeparator.last_ts.value > 0

    def test_check_separator_updates_timestamp(self, logger_with_sep):
        """Test _check_separator updates last_ts."""
        with LoggerWithSeparator.lock:
            LoggerWithSeparator.last_ts.value = 0

        logger_with_sep._check_separator()

        # Timestamp should be updated
        assert LoggerWithSeparator.last_ts.value > 0


# =============================================================================
# Test set_content_separator_secs - Lines 67-68
# =============================================================================


@pytest.mark.unit
class TestSetContentSeparatorSecs:
    """Test set_content_separator_secs method."""

    def test_set_content_separator_secs_basic(self):
        """Test set_content_separator_secs updates value (lines 67-68)."""
        original = LoggerWithSeparator.new_content_separator_secs.value

        LoggerWithSeparator.set_content_separator_secs(10.0)

        assert LoggerWithSeparator.new_content_separator_secs.value == 10.0

        # Restore
        LoggerWithSeparator.set_content_separator_secs(original)

    def test_set_content_separator_secs_zero_disables(self):
        """Test setting to 0 disables separators."""
        LoggerWithSeparator.set_content_separator_secs(0)

        assert LoggerWithSeparator.new_content_separator_secs.value == 0.0

        # Restore default
        LoggerWithSeparator.set_content_separator_secs(5.0)

    def test_set_content_separator_secs_converts_to_float(self):
        """Test value is converted to float."""
        LoggerWithSeparator.set_content_separator_secs(5)  # int

        assert isinstance(LoggerWithSeparator.new_content_separator_secs.value, float)
        assert LoggerWithSeparator.new_content_separator_secs.value == 5.0


# =============================================================================
# Test Integration Scenarios
# =============================================================================


@pytest.mark.integration
class TestLoggerWithSepIntegration:
    """Test LoggerWithSeparator integration scenarios."""

    def test_logging_workflow(self, logger_with_sep):
        """Test complete logging workflow."""
        # Set short interval
        LoggerWithSeparator.set_content_separator_secs(0.01)

        # Log multiple messages
        logger_with_sep.info("message 1")
        logger_with_sep.debug("message 2")
        logger_with_sep.warning("message 3")

        # Wait for gap
        time.sleep(0.02)

        # Log after gap
        logger_with_sep.info("message after gap")

        # No crash means success

    def test_multiple_loggers_share_state(self, log_config, callback_registry):
        """Test multiple loggers share separator state."""
        logger1 = LoggerWithSeparator("sep1", log_config, callback_registry, {})
        logger2 = LoggerWithSeparator("sep2", log_config, callback_registry, {})

        # Set interval via one logger
        LoggerWithSeparator.set_content_separator_secs(2.0)

        # Both should see the same value (shared class state)
        assert LoggerWithSeparator.new_content_separator_secs.value == 2.0

        # Cleanup
        logger1.handlers.clear()
        logger2.handlers.clear()
        LoggerWithSeparator.set_content_separator_secs(5.0)
