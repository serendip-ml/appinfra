"""
E2E test for config file loading workflow.

This test validates the complete workflow from AppBuilder.with_config_file()
through to actual logging output, ensuring logging levels and handlers from
YAML config are correctly applied.

Tests cover:
- YAML logging settings (level, location, micros) are applied
- YAML handlers are loaded and used
- CLI args properly override YAML settings
- Custom config filename works
- Programmatic config (via builder) takes precedence over YAML
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from appinfra.app.builder import AppBuilder


@pytest.mark.e2e
class TestConfigFileWorkflow:
    """E2E tests for config file loading workflow."""

    def test_yaml_logging_level_applied(self):
        """Test that logging level from YAML config is applied to the app."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with debug level
            (etc_dir / "app.yaml").write_text("logging:\n  level: debug\n")

            # Build app with config file from etc-dir
            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            # Simulate running with --etc-dir pointing to our test directory
            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Verify logging level from YAML was applied
            assert app.config.logging.level == "debug"

    def test_yaml_logging_level_not_overridden_by_defaults(self):
        """Regression test: YAML logging level should not be overridden by defaults.

        Previously, App.__init__ created a default config with level='info',
        which then overrode YAML values during merge.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with non-default values
            (etc_dir / "app.yaml").write_text(
                "logging:\n  level: warning\n  location: 2\n  micros: true\n"
            )

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # All YAML values should be preserved
            assert app.config.logging.level == "warning"
            assert app.config.logging.location == 2
            assert app.config.logging.micros is True

    def test_cli_args_override_yaml_config(self):
        """Test that CLI arguments take precedence over YAML config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with info level
            (etc_dir / "app.yaml").write_text("logging:\n  level: info\n")

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            # Pass --log-level debug to override YAML
            with patch.object(
                sys, "argv", ["test", "--etc-dir", str(etc_dir), "--log-level", "debug"]
            ):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # CLI arg should win
            assert app.config.logging.level == "debug"

    def test_custom_config_filename(self):
        """Test that with_config_file(filename) loads only that file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create two config files
            (etc_dir / "default.yaml").write_text(
                "from_default: true\nlogging:\n  level: info\n"
            )
            (etc_dir / "custom.yaml").write_text(
                "from_custom: true\nlogging:\n  level: debug\n"
            )

            app = (
                AppBuilder("test-app")
                .with_config_file("custom.yaml")  # Load only custom.yaml
                .build()
            )

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Should have loaded custom.yaml only
            assert hasattr(app.config, "from_custom")
            assert app.config.from_custom is True
            assert app.config.logging.level == "debug"

            # Should NOT have loaded default.yaml
            assert not hasattr(app.config, "from_default")

    def test_yaml_handlers_loaded(self):
        """Test that handlers defined in YAML config are loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with custom handler
            (etc_dir / "app.yaml").write_text(
                "logging:\n"
                "  level: debug\n"
                "  handlers:\n"
                "    console:\n"
                "      type: console\n"
                "      level: debug\n"
                "      format: text\n"
            )

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Verify handlers section exists in config
            assert hasattr(app.config.logging, "handlers")
            assert hasattr(app.config.logging.handlers, "console")
            assert app.config.logging.handlers.console.type == "console"

    def test_programmatic_config_takes_precedence(self):
        """Test that config set via builder methods takes precedence over YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with debug level
            (etc_dir / "app.yaml").write_text("logging:\n  level: debug\n")

            app = (
                AppBuilder("test-app")
                .with_config_file("app.yaml")
                .logging.with_level("error")  # Programmatic override
                .done()
                .build()
            )

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Programmatic config should win over YAML
            assert app.config.logging.level == "error"

    def test_no_config_file_uses_defaults(self):
        """Test that not using with_config_file uses default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            (etc_dir / "app.yaml").write_text(
                "custom_key: should_not_load\nlogging:\n  level: debug\n"
            )

            # Don't use with_config_file
            app = AppBuilder("test-app").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Should NOT have loaded the YAML config
            assert not hasattr(app.config, "custom_key")

    def test_default_config_file_loaded(self):
        """Test that with_config_file() without args loads infra.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()
            (etc_dir / "infra.yaml").write_text(
                "default_loaded: true\nlogging:\n  level: trace\n"
            )

            # Use with_config_file() without arguments - should use infra.yaml
            app = AppBuilder("test-app").with_config_file().build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Should have loaded infra.yaml
            assert hasattr(app.config, "default_loaded")
            assert app.config.default_loaded is True
            assert app.config.logging.level == "trace"

    def test_full_app_lifecycle_with_yaml_config(self):
        """Test complete app lifecycle with YAML config including logging setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create full config with logging settings
            (etc_dir / "app.yaml").write_text(
                "app_name: e2e-test\nlogging:\n  level: debug\n  location: 1\n"
            )

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            # Run app setup (without running a tool)
            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                try:
                    app.setup()
                    # Verify config was loaded
                    assert app.config.app_name == "e2e-test"
                    assert app.config.logging.level == "debug"
                finally:
                    # Clean up logging handlers to avoid interference
                    if app.lifecycle.logger:
                        app.lifecycle.logger.handlers.clear()

    def test_etc_dir_from_cli_arg(self):
        """Test that --etc-dir CLI arg correctly specifies config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create etc in a non-standard location
            custom_etc = Path(tmpdir) / "custom" / "config" / "etc"
            custom_etc.mkdir(parents=True)

            (custom_etc / "app.yaml").write_text(
                "from_custom_etc: true\nlogging:\n  level: trace\n"
            )

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(custom_etc)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            assert app.config.from_custom_etc is True
            assert app.config.logging.level == "trace"

    def test_missing_config_file_fails_gracefully(self):
        """Test that missing config file doesn't crash the app."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()
            # Don't create any config files

            app = AppBuilder("test-app").with_config_file("nonexistent.yaml").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()

                # Should not raise - loading handles missing files gracefully
                result = app._load_and_merge_config()

            # App should still work with default config
            assert app.config is not None

    def test_yaml_with_all_logging_options(self):
        """Test comprehensive YAML config with all logging options."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()

            # Create config with all logging options
            (etc_dir / "app.yaml").write_text(
                "logging:\n"
                "  level: debug\n"
                "  location: 2\n"
                "  micros: true\n"
                "  handlers:\n"
                "    stdout:\n"
                "      type: console\n"
                "      level: debug\n"
                "      stream: stdout\n"
                "      format: text\n"
                "      colors: true\n"
                "    stderr:\n"
                "      type: console\n"
                "      level: warning\n"
                "      stream: stderr\n"
                "      format: text\n"
                "  topics:\n"
                "    '/db/**': debug\n"
                "    '/api/**': info\n"
            )

            app = AppBuilder("test-app").with_config_file("app.yaml").build()

            with patch.object(sys, "argv", ["test", "--etc-dir", str(etc_dir)]):
                app.create_args()
                app._parsed_args = app.parser.parse_args()
                app._load_and_merge_config()

            # Verify all options loaded correctly
            assert app.config.logging.level == "debug"
            assert app.config.logging.location == 2
            assert app.config.logging.micros is True

            # Verify handlers
            assert hasattr(app.config.logging, "handlers")
            assert app.config.logging.handlers.stdout.type == "console"
            assert app.config.logging.handlers.stdout.stream == "stdout"
            assert app.config.logging.handlers.stderr.level == "warning"

            # Verify topics
            assert hasattr(app.config.logging, "topics")

    def test_absolute_path_loads_immediately(self):
        """Test that absolute path config loads immediately, not from etc-dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in a specific location (not etc-dir)
            config_path = Path(tmpdir) / "direct_config.yaml"
            config_path.write_text("direct_load: true\nlogging:\n  level: trace\n")

            # Use absolute path
            app = AppBuilder("test-app").with_config_file(str(config_path)).build()

            # Config should already be loaded (no need for etc-dir)
            assert hasattr(app.config, "direct_load")
            assert app.config.direct_load is True

    def test_from_etc_dir_false_loads_from_cwd(self):
        """Test that from_etc_dir=False loads relative to cwd."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in tmpdir
            config_path = Path(tmpdir) / "local_config.yaml"
            config_path.write_text("local_load: true\nlogging:\n  level: info\n")

            # Change to tmpdir and load with from_etc_dir=False
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                app = (
                    AppBuilder("test-app")
                    .with_config_file("local_config.yaml", from_etc_dir=False)
                    .build()
                )

                # Config should already be loaded
                assert hasattr(app.config, "local_load")
                assert app.config.local_load is True
            finally:
                os.chdir(old_cwd)
