"""Tests for lifecycle manager hot-reload functionality."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from appinfra.app.core.lifecycle import LifecycleManager
from appinfra.dot_dict import DotDict


@pytest.fixture
def lifecycle_manager():
    """Create a lifecycle manager with mock application."""
    app = MagicMock()
    app._config_path = None
    return LifecycleManager(app)


@pytest.fixture
def mock_config_with_hot_reload():
    """Create config with hot_reload enabled."""
    return DotDict(
        logging=DotDict(
            level="info",
            hot_reload=DotDict(
                enabled=True,
                config_path="/path/to/config.yaml",
                section="logging",
                debounce_ms=500,
            ),
        )
    )


@pytest.fixture
def mock_config_without_hot_reload():
    """Create config without hot_reload."""
    return DotDict(logging=DotDict(level="info"))


@pytest.mark.unit
class TestGetHotReloadConfig:
    """Tests for _get_hot_reload_config method."""

    def test_returns_none_when_no_logging_section(self, lifecycle_manager):
        """Test returns None when config has no logging section."""
        config = DotDict()

        result = lifecycle_manager._get_hot_reload_config(config)

        assert result is None

    def test_returns_none_when_no_hot_reload_section(
        self, lifecycle_manager, mock_config_without_hot_reload
    ):
        """Test returns None when logging has no hot_reload section."""
        result = lifecycle_manager._get_hot_reload_config(
            mock_config_without_hot_reload
        )

        assert result is None

    def test_returns_none_when_hot_reload_disabled(self, lifecycle_manager):
        """Test returns None when hot_reload.enabled is False."""
        config = DotDict(
            logging=DotDict(hot_reload=DotDict(enabled=False, config_path="/path"))
        )

        result = lifecycle_manager._get_hot_reload_config(config)

        assert result is None

    def test_returns_config_when_enabled(
        self, lifecycle_manager, mock_config_with_hot_reload
    ):
        """Test returns hot_reload config when enabled."""
        result = lifecycle_manager._get_hot_reload_config(mock_config_with_hot_reload)

        assert result is not None
        assert result.config_path == "/path/to/config.yaml"


@pytest.mark.unit
class TestResolveHotReloadConfigPath:
    """Tests for _resolve_hot_reload_config_path method."""

    def test_returns_path_from_hot_reload_config(self, lifecycle_manager):
        """Test returns config_path from hot_reload config."""
        hot_reload_config = DotDict(config_path="/explicit/path.yaml")

        result = lifecycle_manager._resolve_hot_reload_config_path(hot_reload_config)

        assert result == "/explicit/path.yaml"

    def test_returns_none_when_no_path(self, lifecycle_manager):
        """Test returns None when no config_path available."""
        hot_reload_config = DotDict()

        result = lifecycle_manager._resolve_hot_reload_config_path(hot_reload_config)

        assert result is None

    def test_uses_application_config_path_as_fallback(self, lifecycle_manager):
        """Test uses application._config_path when hot_reload has no path."""
        lifecycle_manager.application._config_path = "/app/config.yaml"
        hot_reload_config = DotDict()

        result = lifecycle_manager._resolve_hot_reload_config_path(hot_reload_config)

        assert result == "/app/config.yaml"


@pytest.mark.unit
class TestStartHotReloadWatcher:
    """Tests for _start_hot_reload_watcher method."""

    def test_does_nothing_when_no_hot_reload_config(
        self, lifecycle_manager, mock_config_without_hot_reload
    ):
        """Test does nothing when hot_reload is not configured."""
        with patch("appinfra.log.watcher.LogConfigWatcher") as mock_watcher:
            lifecycle_manager._start_hot_reload_watcher(mock_config_without_hot_reload)

            mock_watcher.get_instance.assert_not_called()

    def test_warns_when_no_config_path(self, lifecycle_manager):
        """Test warns when hot_reload enabled but no config path."""
        config = DotDict(
            logging=DotDict(hot_reload=DotDict(enabled=True))  # No config_path
        )
        lifecycle_manager._lifecycle_logger = MagicMock()
        lifecycle_manager.application._config_path = None

        lifecycle_manager._start_hot_reload_watcher(config)

        lifecycle_manager._lifecycle_logger.warning.assert_called_once()

    def test_warns_when_watchdog_not_installed(
        self, lifecycle_manager, mock_config_with_hot_reload
    ):
        """Test warns when watchdog is not installed."""
        lifecycle_manager._lifecycle_logger = MagicMock()

        # Create a mock module that raises ImportError when LogConfigWatcher is accessed
        mock_module = MagicMock()
        mock_module.LogConfigWatcher = property(
            lambda self: (_ for _ in ()).throw(
                ImportError("No module named 'watchdog'")
            )
        )

        # Temporarily remove the real module and add our mock
        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = None  # type: ignore[assignment]

        try:
            lifecycle_manager._configure_and_start_watcher(
                mock_config_with_hot_reload.logging.hot_reload, "/path/to/config.yaml"
            )
        finally:
            # Restore original module
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

        lifecycle_manager._lifecycle_logger.warning.assert_called_once()
        assert "watchdog not installed" in str(
            lifecycle_manager._lifecycle_logger.warning.call_args
        )

    def test_logs_error_on_exception(
        self, lifecycle_manager, mock_config_with_hot_reload
    ):
        """Test logs error when watcher fails to start."""
        lifecycle_manager._lifecycle_logger = MagicMock()

        # Create a mock watcher class that raises on get_instance
        mock_watcher_class = MagicMock()
        mock_watcher_class.get_instance.side_effect = RuntimeError("Test error")

        mock_module = MagicMock()
        mock_module.LogConfigWatcher = mock_watcher_class

        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = mock_module

        try:
            lifecycle_manager._configure_and_start_watcher(
                mock_config_with_hot_reload.logging.hot_reload, "/path/to/config.yaml"
            )
        finally:
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

        lifecycle_manager._lifecycle_logger.error.assert_called_once()


@pytest.mark.unit
class TestStopHotReloadWatcher:
    """Tests for _stop_hot_reload_watcher method."""

    def test_stops_running_watcher(self, lifecycle_manager):
        """Test stops watcher when it's running."""
        lifecycle_manager._lifecycle_logger = MagicMock()

        mock_watcher = MagicMock()
        mock_watcher.is_running.return_value = True

        mock_watcher_class = MagicMock()
        mock_watcher_class.get_instance.return_value = mock_watcher

        mock_module = MagicMock()
        mock_module.LogConfigWatcher = mock_watcher_class

        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = mock_module

        try:
            lifecycle_manager._stop_hot_reload_watcher()
        finally:
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

        mock_watcher.stop.assert_called_once()
        lifecycle_manager._lifecycle_logger.debug.assert_called()

    def test_does_nothing_when_not_running(self, lifecycle_manager):
        """Test does nothing when watcher is not running."""
        lifecycle_manager._lifecycle_logger = MagicMock()

        mock_watcher = MagicMock()
        mock_watcher.is_running.return_value = False

        mock_watcher_class = MagicMock()
        mock_watcher_class.get_instance.return_value = mock_watcher

        mock_module = MagicMock()
        mock_module.LogConfigWatcher = mock_watcher_class

        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = mock_module

        try:
            lifecycle_manager._stop_hot_reload_watcher()
        finally:
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

        mock_watcher.stop.assert_not_called()

    def test_handles_import_error_silently(self, lifecycle_manager):
        """Test handles ImportError silently (watchdog not installed)."""
        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = None  # type: ignore[assignment]

        try:
            # Should not raise
            lifecycle_manager._stop_hot_reload_watcher()
        finally:
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

    def test_logs_error_on_exception(self, lifecycle_manager):
        """Test logs error on other exceptions."""
        lifecycle_manager._lifecycle_logger = MagicMock()

        mock_watcher_class = MagicMock()
        mock_watcher_class.get_instance.side_effect = RuntimeError("Test error")

        mock_module = MagicMock()
        mock_module.LogConfigWatcher = mock_watcher_class

        original_module = sys.modules.get("appinfra.log.watcher")
        sys.modules["appinfra.log.watcher"] = mock_module

        try:
            lifecycle_manager._stop_hot_reload_watcher()
        finally:
            if original_module is not None:
                sys.modules["appinfra.log.watcher"] = original_module
            else:
                del sys.modules["appinfra.log.watcher"]

        lifecycle_manager._lifecycle_logger.error.assert_called_once()
