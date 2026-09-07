# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""Tests for appinfra.app.builder.configurer.version module."""

import logging
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

pytestmark = pytest.mark.unit

from appinfra.app.builder.app import AppBuilder
from appinfra.app.builder.configurer.version import (
    VersionConfigurer,
    _format_modified,
    _log_build_info,
    _log_package_info,
)
from appinfra.version.actions import VersionWithTrackerAction

BUILD_INFO_SRC = 'COMMIT_HASH = "abc123"\nCOMMIT_SHORT = "abc123"\n'


def _startup_hooks(builder: AppBuilder) -> list:
    """Startup callbacks registered on the builder's hook manager."""
    return builder._hooks.get_hooks("startup")


def _make_context(application: object) -> MagicMock:
    """A HookContext stand-in carrying ``application``."""
    context = MagicMock()
    context.application = application
    return context


class TestFormatModified:
    """Tests for _format_modified helper."""

    def test_none_returns_na(self):
        """Test None returns 'n/a'."""
        assert _format_modified(None) == "n/a"

    def test_true_returns_true_string(self):
        """Test True returns 'True'."""
        assert _format_modified(True) == "True"

    def test_false_returns_false_string(self):
        """Test False returns 'False'."""
        assert _format_modified(False) == "False"


class TestLogBuildInfo:
    """Tests for _log_build_info helper."""

    def test_log_unmodified_build(self):
        """Test logging unmodified build uses debug."""
        lg = MagicMock(spec=logging.Logger)
        build_info = Mock()
        build_info.modified = False
        build_info.commit = "abc123"
        build_info.message = None
        build_info.build_time = None

        _log_build_info(lg, build_info)

        lg.debug.assert_called_once()
        assert "build info" in lg.debug.call_args[0]

    def test_log_modified_build(self):
        """Test logging modified build uses warning."""
        lg = MagicMock(spec=logging.Logger)
        build_info = Mock()
        build_info.modified = True
        build_info.commit = "abc123"
        build_info.message = None
        build_info.build_time = None

        _log_build_info(lg, build_info)

        lg.warning.assert_called_once()

    def test_log_with_message(self):
        """Test logging includes commit message when present."""
        lg = MagicMock(spec=logging.Logger)
        build_info = Mock()
        build_info.modified = False
        build_info.commit = "abc123"
        build_info.message = "feat: add feature"
        build_info.message_short = "feat: add feature"
        build_info.build_time = None

        _log_build_info(lg, build_info)

        extra = lg.debug.call_args[1]["extra"]
        assert extra["commit_msg"] == "feat: add feature"

    def test_log_with_build_time(self):
        """Test logging includes timestamp when present."""
        lg = MagicMock(spec=logging.Logger)
        build_info = Mock()
        build_info.modified = False
        build_info.commit = "abc123"
        build_info.message = None
        build_info.build_time = datetime(2025, 12, 1, 10, 30, 0)

        _log_build_info(lg, build_info)

        extra = lg.debug.call_args[1]["extra"]
        assert extra["timestamp"] == "2025-12-01 10:30:00"


class TestLogPackageInfo:
    """Tests for _log_package_info helper."""

    def test_log_unmodified_package(self):
        """Test logging unmodified package uses debug."""
        lg = MagicMock(spec=logging.Logger)
        info = Mock()
        info.modified = False
        info.name = "mypackage"
        info.commit = "def456"
        info.message = None
        info.build_time = None

        _log_package_info(lg, info)

        lg.debug.assert_called_once()
        extra = lg.debug.call_args[1]["extra"]
        assert extra["package"] == "mypackage"
        assert extra["commit"] == "def456"

    def test_log_modified_package(self):
        """Test logging modified package uses warning."""
        lg = MagicMock(spec=logging.Logger)
        info = Mock()
        info.modified = True
        info.name = "mypackage"
        info.commit = "def456"
        info.message = None
        info.build_time = None

        _log_package_info(lg, info)

        lg.warning.assert_called_once()

    def test_log_package_no_commit(self):
        """Test logging package without commit shows n/a."""
        lg = MagicMock(spec=logging.Logger)
        info = Mock()
        info.modified = False
        info.name = "mypackage"
        info.commit = None
        info.message = None
        info.build_time = None

        _log_package_info(lg, info)

        extra = lg.debug.call_args[1]["extra"]
        assert extra["commit"] == "n/a"

    def test_log_package_with_message(self):
        """Test logging includes commit message when present."""
        lg = MagicMock(spec=logging.Logger)
        info = Mock()
        info.modified = False
        info.name = "mypackage"
        info.commit = "def456"
        info.message = "fix: bug fix"
        info.message_short = "fix: bug fix"
        info.build_time = None

        _log_package_info(lg, info)

        extra = lg.debug.call_args[1]["extra"]
        assert extra["commit_msg"] == "fix: bug fix"

    def test_log_package_with_build_time(self):
        """Test logging includes timestamp when present."""
        lg = MagicMock(spec=logging.Logger)
        info = Mock()
        info.modified = False
        info.name = "mypackage"
        info.commit = "def456"
        info.message = None
        info.build_time = datetime(2025, 12, 1, 10, 30, 0)

        _log_package_info(lg, info)

        extra = lg.debug.call_args[1]["extra"]
        assert extra["timestamp"] == "2025-12-01 10:30:00"


class TestVersionConfigurer:
    """Tests for VersionConfigurer class."""

    @pytest.fixture
    def app_builder(self):
        """A real AppBuilder: done() writes to its version fields and hook manager."""
        return AppBuilder("testapp")

    def test_init(self, app_builder):
        """Test VersionConfigurer initialization."""
        configurer = VersionConfigurer(app_builder)
        assert configurer._app_builder is app_builder
        assert configurer._packages == []
        assert configurer._build_info is None
        assert configurer._log_on_startup is True

    def test_with_semver(self, app_builder):
        """Test setting version string."""
        configurer = VersionConfigurer(app_builder)
        result = configurer.with_semver("1.2.3")

        assert result is configurer  # Fluent API
        assert app_builder._version == "1.2.3"

    def test_with_package(self, app_builder):
        """Test tracking a package."""
        configurer = VersionConfigurer(app_builder)
        result = configurer.with_package("mylib")

        assert result is configurer
        assert "mylib" in configurer._packages

    def test_with_multiple_packages(self, app_builder):
        """Test tracking multiple packages."""
        configurer = VersionConfigurer(app_builder)
        configurer.with_package("lib1").with_package("lib2")

        assert "lib1" in configurer._packages
        assert "lib2" in configurer._packages

    def test_with_startup_log(self, app_builder):
        """Test enabling startup logging."""
        configurer = VersionConfigurer(app_builder)
        configurer._log_on_startup = False
        result = configurer.with_startup_log()

        assert result is configurer
        assert configurer._log_on_startup is True

    def test_without_startup_log(self, app_builder):
        """Test disabling startup logging."""
        configurer = VersionConfigurer(app_builder)
        result = configurer.without_startup_log()

        assert result is configurer
        assert configurer._log_on_startup is False

    def test_with_build_info_default_path(self, app_builder, tmp_path, monkeypatch):
        """Test with_build_info uses cwd by default."""
        # Create a fake _build_info.py
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        monkeypatch.chdir(tmp_path)

        configurer = VersionConfigurer(app_builder)
        result = configurer.with_build_info()

        assert result is configurer
        assert configurer._build_info is not None

    def test_with_build_info_string_path(self, app_builder, tmp_path):
        """Test with_build_info with string path."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text('COMMIT_HASH = "def456"\nCOMMIT_SHORT = "def456"\n')

        configurer = VersionConfigurer(app_builder)
        result = configurer.with_build_info(str(build_info_file))

        assert result is configurer
        assert configurer._build_info is not None

    def test_with_build_info_path_object(self, app_builder, tmp_path):
        """Test with_build_info with Path object."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text('COMMIT_HASH = "ghi789"\nCOMMIT_SHORT = "ghi789"\n')

        configurer = VersionConfigurer(app_builder)
        result = configurer.with_build_info(build_info_file)

        assert result is configurer
        assert configurer._build_info is not None

    def test_done_returns_app_builder(self, app_builder):
        """Test done() returns the app builder."""
        configurer = VersionConfigurer(app_builder)
        result = configurer.done()

        assert result is app_builder

    def test_done_with_packages_creates_tracker(self, app_builder):
        """Test done() creates tracker when packages specified."""
        configurer = VersionConfigurer(app_builder)
        configurer.with_package("pytest")
        configurer.done()

        assert app_builder._version_tracker is not None

    def test_done_without_packages_no_tracker(self, app_builder):
        """Test done() doesn't create tracker when no packages."""
        configurer = VersionConfigurer(app_builder)
        configurer.done()

        assert app_builder._version_tracker is None

    def test_done_sets_build_info(self, app_builder, tmp_path):
        """Test done() sets build info on app builder."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        configurer = VersionConfigurer(app_builder)
        configurer.with_build_info(build_info_file)
        configurer.done()

        assert app_builder._build_info is not None

    def test_done_registers_startup_hook(self, app_builder, tmp_path):
        """done() registers one startup hook at priority 90 when logging enabled."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        configurer = VersionConfigurer(app_builder)
        configurer.with_build_info(build_info_file)
        configurer.done()

        assert len(_startup_hooks(app_builder)) == 1
        assert app_builder._hooks._hook_metadata["startup"][0]["priority"] == 90

    def test_done_no_hook_when_logging_disabled(self, app_builder, tmp_path):
        """Test done() doesn't register hook when logging disabled."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        configurer = VersionConfigurer(app_builder)
        configurer.with_build_info(build_info_file)
        configurer.without_startup_log()
        configurer.done()

        assert not app_builder._hooks.has_hooks("startup")

    def test_done_no_hook_when_nothing_to_log(self, app_builder):
        """Test done() doesn't register hook when nothing to log."""
        configurer = VersionConfigurer(app_builder)
        configurer.done()

        # No build_info and no packages = no hook
        assert not app_builder._hooks.has_hooks("startup")

    def test_done_does_not_add_version_argument(self, app_builder):
        """The -v/--version flag is the cli block's, added at build(), not here."""
        configurer = VersionConfigurer(app_builder)
        configurer.with_semver("1.0.0")
        configurer.done()

        assert app_builder._custom_args == []

    def test_call_keyword_form(self, app_builder, tmp_path):
        """__call__ maps keywords onto the chained methods and returns the builder."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        result = app_builder.version(
            semver="2.0.0",
            build_info=build_info_file,
            package=["pytest", "packaging"],
            startup_log=False,
        )

        assert result is app_builder
        assert app_builder._version == "2.0.0"
        assert app_builder._build_info is not None
        assert app_builder._version_tracker is not None
        assert not app_builder._hooks.has_hooks("startup")


class TestVersionFlag:
    """The cli block's ``version`` flag exposes ``-v/--version`` at build()."""

    @staticmethod
    def _version_arg(builder: AppBuilder) -> tuple[tuple, dict]:
        matches = [(a, kw) for a, kw in builder._custom_args if "--version" in a]
        assert len(matches) == 1
        return matches[0]

    def test_build_adds_version_argument(self):
        """build() appends -v/--version bound to the version block's text."""
        builder = AppBuilder("testapp").version(semver="1.0.0").cli(version=True)
        builder.build()

        args, kwargs = self._version_arg(builder)
        assert args == ("-v", "--version")
        assert kwargs["action"] is VersionWithTrackerAction
        assert kwargs["app_name"] == "testapp"
        assert kwargs["app_version"] == "1.0.0"
        assert kwargs["tracker"] is None
        assert kwargs["build_info"] is None

    def test_no_version_argument_without_cli_flag(self):
        """A semver alone does not expose the flag."""
        builder = AppBuilder("testapp").version(semver="1.0.0")
        builder.build()

        assert builder._custom_args == []

    def test_build_raises_when_flag_on_without_semver(self):
        """The flag needs text to print; build() refuses without a semver."""
        builder = AppBuilder("testapp").cli(version=True)

        with pytest.raises(ValueError, match="with_semver"):
            builder.build()

    def test_version_argument_includes_build_info(self, tmp_path):
        """build_info set on the version block reaches the argument."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        builder = (
            AppBuilder("testapp")
            .version.with_semver("1.0.0")
            .with_build_info(build_info_file)
            .done()
            .cli(version=True)
        )
        builder.build()

        _, kwargs = self._version_arg(builder)
        assert kwargs["build_info"] is builder._build_info
        assert kwargs["build_info"].commit == "abc123"

    def test_version_argument_includes_tracker(self):
        """A tracked package produces a tracker that reaches the argument."""
        builder = (
            AppBuilder("testapp")
            .version(semver="1.0.0", package="pytest")
            .cli(version=True)
        )
        builder.build()

        _, kwargs = self._version_arg(builder)
        assert kwargs["tracker"] is not None
        assert kwargs["tracker"] is builder._version_tracker

    def test_version_argument_takes_presentation_override(self):
        """cli.with_flag('version', ...) merges into the argument's kwargs."""
        builder = (
            AppBuilder("testapp")
            .version(semver="1.0.0")
            .cli.with_flags(version=True)
            .with_flag("version", help="Print version and exit")
            .done()
        )
        builder.build()

        _, kwargs = self._version_arg(builder)
        assert kwargs["help"] == "Print version and exit"

    def test_version_argument_added_once_across_builds(self):
        """A second build() does not append a duplicate argument."""
        builder = AppBuilder("testapp").version(semver="1.0.0").cli(version=True)
        builder.build()
        builder.build()

        self._version_arg(builder)


class TestStartupHookBehavior:
    """Tests for the startup hook callback behavior."""

    def test_startup_hook_logs_build_info(self, tmp_path):
        """Test startup hook actually logs build info when invoked."""
        build_info_file = tmp_path / "_build_info.py"
        build_info_file.write_text(BUILD_INFO_SRC)

        builder = AppBuilder("testapp")
        VersionConfigurer(builder).with_build_info(build_info_file).done()

        hooks = _startup_hooks(builder)
        assert hooks

        mock_app = MagicMock()
        mock_app.lg = MagicMock(spec=logging.Logger)
        for callback in hooks:
            callback(_make_context(mock_app))

        # Verify build info was logged
        mock_app.lg.debug.assert_called()

    def test_startup_hook_logs_packages(self):
        """Test startup hook logs tracked packages when invoked."""
        builder = AppBuilder("testapp")
        VersionConfigurer(builder).with_package("pytest").done()  # a real package

        hooks = _startup_hooks(builder)
        assert hooks

        mock_app = MagicMock()
        mock_app.lg = MagicMock(spec=logging.Logger)
        for callback in hooks:
            callback(_make_context(mock_app))

        # Verify package was logged
        mock_app.lg.debug.assert_called()

    def test_startup_hook_handles_missing_logger(self):
        """Test startup hook handles application without lg attribute."""
        builder = AppBuilder("testapp")
        VersionConfigurer(builder).with_package("pytest").done()

        hooks = _startup_hooks(builder)
        assert hooks

        # Should not raise - callback returns early
        for callback in hooks:
            callback(_make_context(MagicMock(spec=[])))  # No lg attribute
