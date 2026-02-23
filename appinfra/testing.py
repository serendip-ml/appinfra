"""
Generic pytest utilities for appinfra-based projects.

This module provides pytest markers and hooks for common testing patterns.
Use as a pytest plugin by adding to your conftest.py:

    pytest_plugins = ["appinfra.testing"]

Markers:
    expected_skip: Mark tests where skipping is expected/acceptable.
        These skips won't appear in check.sh warning summaries.

Example:
    @pytest.mark.expected_skip
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_paths():
        ...
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.nodes import Item
    from _pytest.reports import TestReport
    from _pytest.runner import CallInfo


# Prefix added to skip reasons for expected skips (filtered by check.sh)
EXPECTED_SKIP_PREFIX = "[expected] "


def pytest_configure(config: Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "expected_skip: Mark test where skipping is expected/acceptable. "
        "These skips won't appear in check.sh warning summaries.",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: Item, call: CallInfo
) -> Generator[None, None, None]:
    """
    Modify skip reason for tests marked with expected_skip.

    When a test with the expected_skip marker is skipped, this hook prefixes
    the skip reason with '[expected] ' so that check.sh can filter it out
    of the warning summary.
    """
    outcome: Any = yield
    report: TestReport = outcome.get_result()

    # Only process skipped tests in the call phase (not setup/teardown)
    if report.skipped and call.when == "call":
        # Check if test has expected_skip marker
        if item.get_closest_marker("expected_skip"):
            _prefix_skip_reason(report)

    # Also handle setup-phase skips (e.g., skipif evaluated during setup)
    if report.skipped and call.when == "setup":
        if item.get_closest_marker("expected_skip"):
            _prefix_skip_reason(report)


def _prefix_skip_reason(report: TestReport) -> None:
    """Add [expected] prefix to a skip report's reason."""
    # report.longrepr is a tuple: (file, line, reason)
    if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
        file_path, line, reason = report.longrepr
        if not reason.startswith(EXPECTED_SKIP_PREFIX):
            report.longrepr = (file_path, line, f"{EXPECTED_SKIP_PREFIX}{reason}")
