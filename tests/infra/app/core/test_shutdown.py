"""
Tests for app/core/shutdown.py.

Tests shutdown manager functionality including:
- Signal handler registration
- Signal handling (SIGTERM, SIGINT)
- Duplicate signal handling
- Return code mapping
"""

import signal
from unittest.mock import Mock, patch

import pytest

from appinfra.app.core.shutdown import ShutdownManager


@pytest.mark.unit
class TestShutdownManagerInit:
    """Test ShutdownManager initialization."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        callback = Mock()
        manager = ShutdownManager(callback, timeout=30.0)

        assert manager._shutdown_callback is callback
        assert manager._timeout == 30.0
        assert manager._shutting_down is False
        assert manager._original_handlers == {}

    def test_default_timeout(self):
        """Test default timeout value."""
        callback = Mock()
        manager = ShutdownManager(callback)

        assert manager._timeout == 30.0


@pytest.mark.unit
class TestSignalRegistration:
    """Test signal handler registration."""

    def test_register_signal_handlers(self):
        """Test register_signal_handlers registers SIGTERM and SIGINT."""
        callback = Mock()
        manager = ShutdownManager(callback)

        with patch("signal.signal") as mock_signal:
            mock_signal.return_value = Mock()  # Original handler
            manager.register_signal_handlers()

            # Should register both SIGTERM and SIGINT
            assert mock_signal.call_count == 2
            calls = mock_signal.call_args_list
            signals_registered = [call[0][0] for call in calls]
            assert signal.SIGTERM in signals_registered
            assert signal.SIGINT in signals_registered

    def test_original_handlers_preserved(self):
        """Test that original signal handlers are preserved."""
        callback = Mock()
        manager = ShutdownManager(callback)

        mock_term_handler = Mock()
        mock_int_handler = Mock()

        with patch("signal.signal") as mock_signal:

            def signal_side_effect(signum, handler):
                if signum == signal.SIGTERM:
                    return mock_term_handler
                elif signum == signal.SIGINT:
                    return mock_int_handler

            mock_signal.side_effect = signal_side_effect
            manager.register_signal_handlers()

            assert manager._original_handlers[signal.SIGTERM] is mock_term_handler
            assert manager._original_handlers[signal.SIGINT] is mock_int_handler


@pytest.mark.unit
class TestSignalHandling:
    """Test signal handling logic."""

    def test_handle_sigint_sets_return_code_130(self):
        """Test SIGINT handler uses return code 130."""
        callback = Mock(return_value=130)
        manager = ShutdownManager(callback)

        with patch("sys.exit") as mock_exit:
            manager._handle_signal(signal.SIGINT, None)

            callback.assert_called_once_with(130)
            mock_exit.assert_called_once_with(130)

    def test_handle_sigterm_sets_return_code_143(self):
        """Test SIGTERM handler uses return code 143."""
        callback = Mock(return_value=143)
        manager = ShutdownManager(callback)

        with patch("sys.exit") as mock_exit:
            manager._handle_signal(signal.SIGTERM, None)

            callback.assert_called_once_with(143)
            mock_exit.assert_called_once_with(143)

    def test_handle_signal_sets_shutting_down_flag(self):
        """Test signal handler sets shutting_down flag."""
        callback = Mock(return_value=0)
        manager = ShutdownManager(callback)

        with patch("sys.exit"):
            assert manager._shutting_down is False
            manager._handle_signal(signal.SIGINT, None)
            assert manager._shutting_down is True

    def test_duplicate_signal_ignored(self):
        """Test duplicate signal is ignored when already shutting down."""
        callback = Mock(return_value=0)
        manager = ShutdownManager(callback)
        manager._shutting_down = True  # Already shutting down

        with patch("sys.exit") as mock_exit:
            manager._handle_signal(signal.SIGINT, None)

            # Callback should not be called again
            callback.assert_not_called()
            mock_exit.assert_not_called()

    def test_handle_signal_exception_exits_with_1(self):
        """Test signal handler exits with code 1 on exception."""
        callback = Mock(side_effect=RuntimeError("Shutdown failed"))
        manager = ShutdownManager(callback)

        with patch("sys.exit") as mock_exit, patch("logging.error") as mock_log_error:
            manager._handle_signal(signal.SIGINT, None)

            mock_log_error.assert_called_once()
            mock_exit.assert_called_once_with(1)


@pytest.mark.unit
class TestIsShuttingDown:
    """Test is_shutting_down method."""

    def test_is_shutting_down_false_initially(self):
        """Test is_shutting_down returns False initially."""
        callback = Mock()
        manager = ShutdownManager(callback)

        assert manager.is_shutting_down() is False

    def test_is_shutting_down_true_after_signal(self):
        """Test is_shutting_down returns True after signal handled."""
        callback = Mock(return_value=0)
        manager = ShutdownManager(callback)

        with patch("sys.exit"):
            manager._handle_signal(signal.SIGINT, None)

        assert manager.is_shutting_down() is True
