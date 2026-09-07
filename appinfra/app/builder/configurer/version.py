# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Version block for AppBuilder.

Declares the app version and tracks commit hashes of packages that use
the appinfra build protocol (``_build_info.py``). Exposing ``-v/--version``
is the ``.cli`` block's ``version`` flag; this block supplies its text.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, TypedDict, Unpack

if TYPE_CHECKING:
    from ....version import BuildInfo, PackageVersionInfo
    from ..app import AppBuilder


class VersionFields(TypedDict, total=False):
    """Keyword form of the version block; see ``VersionConfigurer.__call__``."""

    semver: str
    build_info: bool | str | Path
    package: str | Sequence[str]
    startup_log: bool


def _format_modified(val: bool | None) -> str:
    """Format modified status for logging."""
    if val is None:
        return "n/a"
    return str(val)


def _log_build_info(lg: logging.Logger, build_info: BuildInfo) -> None:
    """Log the app's own build info."""
    modified = build_info.modified
    extra: dict[str, object] = {
        "modified": _format_modified(modified),
        "commit": build_info.commit,
    }
    if build_info.message:
        extra["commit_msg"] = build_info.message_short
    if build_info.build_time:
        extra["timestamp"] = build_info.build_time.strftime("%Y-%m-%d %H:%M:%S")

    if modified:
        lg.warning("build info", extra=extra)
    else:
        lg.debug("build info", extra=extra)


def _log_package_info(lg: logging.Logger, info: PackageVersionInfo) -> None:
    """Log a tracked package's version info."""
    modified = info.modified
    extra: dict[str, object] = {
        "modified": _format_modified(modified),
        "package": info.name,
        "commit": info.commit or "n/a",
    }
    if info.message:
        extra["commit_msg"] = info.message_short
    if info.build_time:
        extra["timestamp"] = info.build_time.strftime("%Y-%m-%d %H:%M:%S")

    if modified:
        lg.warning("package", extra=extra)
    else:
        lg.debug("package", extra=extra)


class VersionConfigurer:
    """Version block: semver, build info, tracked packages, startup logging.

    Chained::

        AppBuilder("myapp").version.with_semver("1.0.0").with_build_info().done()

    Keyword, returning the AppBuilder directly::

        AppBuilder("myapp").version(semver="1.0.0", build_info=True, package="mylib")
    """

    def __init__(self, app_builder: AppBuilder):
        """Bind the block to its parent builder."""
        self._app_builder = app_builder
        self._packages: list[str] = []
        self._build_info: BuildInfo | None = None
        self._log_on_startup = True

    def with_semver(self, version: str) -> Self:
        """Set the application version string (e.g., '1.0.0')."""
        self._app_builder._version = version
        return self

    def with_build_info(self, path: Path | str | None = None) -> Self:
        """
        Include build info for the current repo.

        Reads _build_info.py to get the app's own commit hash.

        Args:
            path: Path to _build_info.py. If None, looks in the package directory
                  (based on app name), falling back to current directory.

        Returns:
            Self for method chaining
        """
        from ....version import BuildInfo

        if path is None:
            path = self._find_build_info_path()
        elif isinstance(path, str):
            path = Path(path)

        self._build_info = BuildInfo.from_path(path)
        return self

    def _find_build_info_path(self) -> Path:
        """Find _build_info.py in package directory or fall back to cwd."""
        import importlib.util

        app_name = self._app_builder._name
        if app_name:
            # Try to find the package and look for _build_info.py there
            spec = importlib.util.find_spec(app_name)
            if spec and spec.origin:
                pkg_path = Path(spec.origin).parent / "_build_info.py"
                if pkg_path.exists():
                    return pkg_path

        # Fall back to current directory
        return Path.cwd() / "_build_info.py"

    def with_package(self, name: str) -> Self:
        """Track a specific package by distribution name."""
        self._packages.append(name)
        return self

    def with_startup_log(self) -> Self:
        """Enable startup logging of package versions (default)."""
        self._log_on_startup = True
        return self

    def without_startup_log(self) -> Self:
        """Disable startup logging of package versions."""
        self._log_on_startup = False
        return self

    def done(self) -> AppBuilder:
        """Finish version configuration and return to main builder."""
        from ....version import PackageVersionTracker

        tracker: PackageVersionTracker | None = None
        if self._packages:
            tracker = PackageVersionTracker()
            tracker.track(*self._packages)
            self._app_builder._version_tracker = tracker

        if self._build_info is not None:
            self._app_builder._build_info = self._build_info

        if self._log_on_startup and (self._build_info or tracker):
            self._register_startup_hook(tracker, self._build_info)

        return self._app_builder

    def _register_startup_hook(
        self, tracker: Any, build_info: BuildInfo | None
    ) -> None:
        """Register a startup hook to log version info."""
        from ..hook import HookContext

        def log_versions(context: HookContext) -> None:
            if not hasattr(context.application, "lg"):
                return

            if build_info:
                _log_build_info(context.application.lg, build_info)

            if tracker and len(tracker) > 0:
                for info in tracker.get_all().values():
                    _log_package_info(context.application.lg, info)

        self._app_builder._hooks.register_hook("startup", log_versions, priority=90)

    def __call__(self, **fields: Unpack[VersionFields]) -> AppBuilder:
        """Keyword form of the block; returns the AppBuilder."""
        if "semver" in fields:
            self.with_semver(fields["semver"])
        build_info = fields.get("build_info")
        if build_info is True:
            self.with_build_info()
        elif isinstance(build_info, str | Path):
            self.with_build_info(build_info)
        package = fields.get("package")
        if isinstance(package, str):
            self.with_package(package)
        elif package is not None:
            for name in package:
                self.with_package(name)
        if fields.get("startup_log") is False:
            self.without_startup_log()
        return self.done()
