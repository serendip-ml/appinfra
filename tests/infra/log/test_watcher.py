"""Tests for LogConfigWatcher - file-based hot-reload."""

import pytest

from appinfra.log.watcher import LogConfigWatcher


@pytest.fixture(autouse=True)
def reset_watcher():
    """Reset singleton before and after each test."""
    LogConfigWatcher.reset_instance()
    yield
    LogConfigWatcher.reset_instance()


@pytest.mark.unit
class TestLogConfigWatcher:
    """Unit tests for LogConfigWatcher."""

    def test_singleton_instance(self):
        """Test that get_instance returns singleton."""
        instance1 = LogConfigWatcher.get_instance()
        instance2 = LogConfigWatcher.get_instance()

        assert instance1 is instance2

    def test_reset_instance(self):
        """Test that reset_instance creates new instance."""
        instance1 = LogConfigWatcher.get_instance()
        LogConfigWatcher.reset_instance()
        instance2 = LogConfigWatcher.get_instance()

        assert instance1 is not instance2

    def test_configure_sets_path(self, tmp_path):
        """Test configure sets config path."""
        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        result = watcher.configure(str(config_file))

        assert result is watcher  # Fluent API
        assert watcher._config_path == config_file.resolve()

    def test_configure_sets_section(self, tmp_path):
        """Test configure sets section."""
        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher.configure(str(config_file), section="custom.logging")

        assert watcher._section == "custom.logging"

    def test_configure_sets_debounce(self, tmp_path):
        """Test configure sets debounce."""
        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher.configure(str(config_file), debounce_ms=1000)

        assert watcher._debounce_ms == 1000

    def test_is_running_initially_false(self):
        """Test watcher is not running initially."""
        watcher = LogConfigWatcher.get_instance()

        assert watcher.is_running() is False

    def test_start_without_configure_raises(self):
        """Test start without configure raises ValueError (or ImportError if watchdog not installed)."""
        watcher = LogConfigWatcher.get_instance()

        # May raise ImportError if watchdog not installed, or ValueError if it is
        with pytest.raises((ValueError, ImportError)):
            watcher.start()

    def test_stop_when_not_running_does_nothing(self):
        """Test stop when not running doesn't raise."""
        watcher = LogConfigWatcher.get_instance()

        # Should not raise
        watcher.stop()
        assert watcher.is_running() is False

    def test_add_reload_callback(self):
        """Test adding reload callback."""
        watcher = LogConfigWatcher.get_instance()
        results = []

        def callback(config):
            results.append(config)

        watcher.add_reload_callback(callback)

        assert callback in watcher._on_reload_callbacks

    def test_remove_reload_callback(self):
        """Test removing reload callback."""
        watcher = LogConfigWatcher.get_instance()

        def callback(config):
            pass

        watcher.add_reload_callback(callback)
        watcher.remove_reload_callback(callback)

        assert callback not in watcher._on_reload_callbacks

    def test_remove_nonexistent_callback_does_not_error(self):
        """Test removing non-existent callback doesn't raise."""
        watcher = LogConfigWatcher.get_instance()

        def callback(config):
            pass

        # Should not raise
        watcher.remove_reload_callback(callback)


@pytest.mark.unit
class TestLogConfigWatcherDebounce:
    """Tests for debounce behavior."""

    def test_debounce_blocks_rapid_reloads(self, tmp_path):
        """Test that debounce prevents rapid reloads."""
        import time

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher.configure(str(config_file), debounce_ms=500)

        # Simulate rapid file changes
        watcher._last_reload = time.time() * 1000  # Set last reload to now

        reload_count = 0

        original_reload = watcher._reload_config

        def counting_reload():
            nonlocal reload_count
            reload_count += 1
            original_reload()

        watcher._reload_config = counting_reload

        # These should all be debounced
        watcher._on_file_changed()
        watcher._on_file_changed()
        watcher._on_file_changed()

        assert reload_count == 0  # All debounced


@pytest.mark.integration
class TestLogConfigWatcherIntegration:
    """Integration tests for LogConfigWatcher (without watchdog)."""

    def test_reload_now_updates_registry(self, tmp_path):
        """Test reload_now updates config registry."""
        from appinfra.log.config_registry import LogConfigRegistry

        # Reset registry
        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: debug\n  location: 2\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        registry = LogConfigRegistry.get_instance()
        holder = registry.create_holder()

        # Initial state
        assert holder.level == 20  # INFO (default)

        # Reload
        watcher.reload_now()

        # After reload - holder should be updated
        assert holder.level == 10  # DEBUG
        assert holder.location == 2

        # Cleanup
        LogConfigRegistry.reset_instance()

    def test_reload_now_notifies_callbacks(self, tmp_path):
        """Test reload_now notifies callbacks."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: debug\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        results = []
        watcher.add_reload_callback(lambda c: results.append(c.level))

        watcher.reload_now()

        assert len(results) == 1
        assert results[0] == 10  # DEBUG

        LogConfigRegistry.reset_instance()

    def test_reload_handles_invalid_config(self, tmp_path, capsys):
        """Test reload handles invalid config gracefully."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("invalid: yaml: content: [")  # Invalid YAML

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        # Should not raise
        watcher.reload_now()

        # Should print error to stderr
        captured = capsys.readouterr()
        assert "Failed to reload config" in captured.err

    def test_reload_without_config_path_does_nothing(self):
        """Test reload_now does nothing when config_path is None."""
        watcher = LogConfigWatcher.get_instance()
        # Don't call configure, so _config_path is None

        # Should not raise
        watcher.reload_now()

    def test_callback_error_does_not_break_reload(self, tmp_path):
        """Test that callback errors don't prevent other callbacks."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: debug\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        results = []
        watcher.add_reload_callback(lambda c: results.append("first"))
        watcher.add_reload_callback(lambda c: 1 / 0)  # Raises ZeroDivisionError
        watcher.add_reload_callback(lambda c: results.append("third"))

        watcher.reload_now()

        # First and third should have run despite second raising
        assert results == ["first", "third"]

        LogConfigRegistry.reset_instance()

    def test_on_file_changed_calls_reload_after_debounce(self, tmp_path):
        """Test _on_file_changed calls _reload_config when debounce passed."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: debug\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file), debounce_ms=0)  # No debounce

        reload_count = 0

        original_reload = watcher._reload_config

        def counting_reload():
            nonlocal reload_count
            reload_count += 1
            original_reload()

        watcher._reload_config = counting_reload

        # Should not be debounced with debounce_ms=0
        watcher._on_file_changed()

        assert reload_count == 1

        LogConfigRegistry.reset_instance()


@pytest.mark.unit
class TestLogConfigWatcherUpdateLevelManager:
    """Tests for _update_level_manager method."""

    def test_update_level_manager_with_topics(self, tmp_path):
        """Test _update_level_manager updates LogLevelManager with topics."""
        from appinfra.log.level_manager import LogLevelManager

        LogLevelManager.reset_instance()

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")
        watcher.configure(str(config_file))

        config_dict = {
            "logging": {
                "level": "debug",
                "topics": {
                    "/app.*": "debug",
                    "/db.*": "warning",
                },
            }
        }

        watcher._update_level_manager(config_dict)

        manager = LogLevelManager.get_instance()
        # Check rules were added (returns string, not int)
        assert manager.get_effective_level("app.foo") == "debug"
        assert manager.get_effective_level("db.query") == "warning"

        LogLevelManager.reset_instance()

    def test_update_level_manager_with_nested_section(self, tmp_path):
        """Test _update_level_manager with nested section path."""
        from appinfra.log.level_manager import LogLevelManager

        LogLevelManager.reset_instance()

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("app:\n  logging:\n    level: info\n")
        watcher.configure(str(config_file), section="app.logging")

        config_dict = {
            "app": {
                "logging": {
                    "level": "debug",
                    "topics": {
                        "/custom.*": "error",
                    },
                }
            }
        }

        watcher._update_level_manager(config_dict)

        manager = LogLevelManager.get_instance()
        assert manager.get_effective_level("custom.module") == "error"

        LogLevelManager.reset_instance()

    def test_update_level_manager_missing_section_does_nothing(self, tmp_path):
        """Test _update_level_manager returns early if section not found."""
        from appinfra.log.level_manager import LogLevelManager

        LogLevelManager.reset_instance()

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")
        watcher.configure(str(config_file), section="nonexistent.section")

        config_dict = {"logging": {"level": "debug"}}

        # Should not raise
        watcher._update_level_manager(config_dict)

        LogLevelManager.reset_instance()

    def test_update_level_manager_section_not_dict_does_nothing(self, tmp_path):
        """Test _update_level_manager returns early if section is not a dict."""
        from appinfra.log.level_manager import LogLevelManager

        LogLevelManager.reset_instance()

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging: not_a_dict\n")
        watcher.configure(str(config_file))

        config_dict = {"logging": "not_a_dict"}

        # Should not raise
        watcher._update_level_manager(config_dict)

        LogLevelManager.reset_instance()

    def test_update_level_manager_no_topics_does_nothing(self, tmp_path):
        """Test _update_level_manager does nothing when no topics in config."""
        from appinfra.log.level_manager import LogLevelManager

        LogLevelManager.reset_instance()

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")
        watcher.configure(str(config_file))

        config_dict = {"logging": {"level": "debug"}}  # No topics

        # Should not raise
        watcher._update_level_manager(config_dict)

        LogLevelManager.reset_instance()


@pytest.mark.unit
class TestLogConfigWatcherReloadPaths:
    """Tests for reload configuration paths."""

    def test_reload_config_applies_config_and_notifies(self, tmp_path):
        """Test _reload_config applies config and notifies callbacks."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: warning\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        callback_results = []
        watcher.add_reload_callback(lambda cfg: callback_results.append(cfg.level))

        # Call the internal _reload_config directly
        watcher._reload_config()

        # Callback should have been notified
        assert len(callback_results) == 1
        assert callback_results[0] == 30  # WARNING level

        LogConfigRegistry.reset_instance()

    def test_apply_config_update_returns_log_config(self, tmp_path):
        """Test _apply_config_update returns the new LogConfig."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: error\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        config_dict = {"logging": {"level": "error", "location": 1}}

        result = watcher._apply_config_update(config_dict)

        assert result.level == 40  # ERROR level
        assert result.location == 1

        LogConfigRegistry.reset_instance()

    def test_notify_callbacks_handles_exceptions(self, tmp_path):
        """Test _notify_callbacks doesn't break when callback raises."""
        from appinfra.log.config import LogConfig

        watcher = LogConfigWatcher.get_instance()
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")
        watcher.configure(str(config_file))

        results = []

        def good_callback(cfg):
            results.append("good1")

        def bad_callback(cfg):
            raise ValueError("intentional error")

        def good_callback2(cfg):
            results.append("good2")

        watcher.add_reload_callback(good_callback)
        watcher.add_reload_callback(bad_callback)
        watcher.add_reload_callback(good_callback2)

        # Create a mock LogConfig to pass to callbacks
        mock_config = LogConfig(level=20, location=0)

        # Call _notify_callbacks directly
        watcher._notify_callbacks(mock_config)

        # Both good callbacks should have run
        assert results == ["good1", "good2"]

    def test_on_file_changed_triggers_reload_after_debounce(self, tmp_path):
        """Test _on_file_changed triggers reload when debounce time has passed."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file), debounce_ms=0)  # No debounce
        watcher._last_reload = 0  # Reset last reload time to distant past

        reload_called = []
        original_reload = watcher._reload_config

        def tracking_reload():
            reload_called.append(True)
            original_reload()

        watcher._reload_config = tracking_reload

        # This should trigger reload since debounce=0 and last_reload=0
        watcher._on_file_changed()

        assert len(reload_called) == 1

        LogConfigRegistry.reset_instance()

    def test_reload_config_with_none_path_returns_early(self):
        """Test _reload_config returns early when config_path is None."""
        watcher = LogConfigWatcher.get_instance()
        # Don't configure, so _config_path is None

        # Should not raise - just return early
        watcher._reload_config()

        # No error means success

    def test_create_file_handler_matches_config_path(self, tmp_path):
        """Test _create_file_handler creates handler that checks correct path."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        handler = watcher._create_file_handler()

        # Handler should be a FileSystemEventHandler subclass
        assert handler is not None
        assert hasattr(handler, "on_modified")


# =============================================================================
# Test Watching Included Files
# =============================================================================


@pytest.mark.unit
class TestLogConfigWatcherIncludedFiles:
    """Tests for watching included configuration files."""

    def test_get_source_files_from_config_includes_all_files(self, tmp_path):
        """Test _get_source_files_from_config returns main and included files."""
        # Create included logging config
        logging_file = tmp_path / "logging.yaml"
        logging_file.write_text("level: debug\n")

        # Create main config with include
        config_file = tmp_path / "config.yaml"
        config_file.write_text('logging: !include "./logging.yaml"\napp: test\n')

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        source_files = watcher._get_source_files_from_config()

        assert config_file.resolve() in source_files
        assert logging_file.resolve() in source_files
        assert len(source_files) == 2

    def test_get_source_files_from_config_fallback_on_error(self, tmp_path):
        """Test _get_source_files_from_config returns main file on error."""
        config_file = tmp_path / "config.yaml"
        # Don't create the file - will cause error

        watcher = LogConfigWatcher.get_instance()
        watcher._config_path = config_file  # Set directly without loading

        source_files = watcher._get_source_files_from_config()

        # Should fall back to just the main config file
        assert config_file in source_files

    def test_watched_files_includes_all_source_files(self, tmp_path):
        """Test that _watched_files is populated with all source files on start."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        # Create included file
        logging_file = tmp_path / "logging.yaml"
        logging_file.write_text("level: info\n")

        # Create main config
        config_file = tmp_path / "config.yaml"
        config_file.write_text('logging: !include "./logging.yaml"\n')

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        # Before start, _watched_files should be empty
        assert len(watcher._watched_files) == 0

        # Start will populate _watched_files
        watcher.start()

        try:
            assert config_file.resolve() in watcher._watched_files
            assert logging_file.resolve() in watcher._watched_files
        finally:
            watcher.stop()
            LogConfigRegistry.reset_instance()

    def test_stop_clears_watched_files(self, tmp_path):
        """Test that stop() clears _watched_files and _watched_dirs."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        config_file = tmp_path / "config.yaml"
        config_file.write_text("logging:\n  level: info\n")

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))
        watcher.start()

        # Should have watched files
        assert len(watcher._watched_files) > 0

        watcher.stop()

        # Should be cleared
        assert len(watcher._watched_files) == 0
        assert len(watcher._watched_dirs) == 0

        LogConfigRegistry.reset_instance()

    def test_reload_updates_watched_files(self, tmp_path):
        """Test that reload updates _watched_files when includes change."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        # Create initial include
        logging_file = tmp_path / "logging.yaml"
        logging_file.write_text("level: info\n")

        # Create main config
        config_file = tmp_path / "config.yaml"
        config_file.write_text('logging: !include "./logging.yaml"\n')

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))

        # Manually set watched files (simulating start())
        watcher._watched_files = {config_file.resolve(), logging_file.resolve()}

        # Create a new include file
        new_logging_file = tmp_path / "new_logging.yaml"
        new_logging_file.write_text("level: debug\n")

        # Update config to use new include
        config_file.write_text('logging: !include "./new_logging.yaml"\n')

        # Trigger reload
        watcher._reload_config()

        # _watched_files should now include the new file
        assert new_logging_file.resolve() in watcher._watched_files

        LogConfigRegistry.reset_instance()

    def test_file_handler_triggers_on_included_file_change(self, tmp_path):
        """Test that file handler triggers reload when included file changes."""
        from unittest.mock import MagicMock

        # Create included file
        logging_file = tmp_path / "logging.yaml"
        logging_file.write_text("level: info\n")

        # Create main config
        config_file = tmp_path / "config.yaml"
        config_file.write_text('logging: !include "./logging.yaml"\n')

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file), debounce_ms=0)
        watcher._watched_files = {config_file.resolve(), logging_file.resolve()}
        watcher._last_reload = 0

        # Mock the reload method
        reload_calls = []
        original_reload = watcher._reload_config
        watcher._reload_config = lambda: reload_calls.append(True)

        try:
            handler = watcher._create_file_handler()

            # Create mock event for included file modification
            mock_event = MagicMock()
            mock_event.is_directory = False
            mock_event.src_path = str(logging_file)

            # Trigger handler
            handler.on_modified(mock_event)

            # Should have triggered reload
            assert len(reload_calls) == 1
        finally:
            watcher._reload_config = original_reload

    def test_watches_multiple_directories(self, tmp_path):
        """Test that watcher can watch files in multiple directories."""
        from appinfra.log.config_registry import LogConfigRegistry

        LogConfigRegistry.reset_instance()

        # Create subdirectory for includes
        sub_dir = tmp_path / "includes"
        sub_dir.mkdir()

        # Create included file in subdirectory
        logging_file = sub_dir / "logging.yaml"
        logging_file.write_text("level: info\n")

        # Create main config in root
        config_file = tmp_path / "config.yaml"
        config_file.write_text('logging: !include "./includes/logging.yaml"\n')

        watcher = LogConfigWatcher.get_instance()
        watcher.configure(str(config_file))
        watcher.start()

        try:
            # Should watch both directories
            assert tmp_path in watcher._watched_dirs
            assert sub_dir in watcher._watched_dirs
        finally:
            watcher.stop()
            LogConfigRegistry.reset_instance()
