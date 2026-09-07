# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""Subprocess and IPC configuration builder."""

from __future__ import annotations

import multiprocessing as mp
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

from ..config.api import ApiConfig
from ..config.ipc import IPCConfig

if TYPE_CHECKING:
    from .server import ServerBuilder

# The parent's concrete type, so done() on a subclass of ServerBuilder
# (the AppBuilder server scope) returns that subclass.
P = TypeVar("P", bound="ServerBuilder")

_API_DEFAULTS = ApiConfig()


class SubprocessConfigurer(Generic[P]):
    """
    Focused builder for subprocess and IPC configuration.

    Follows appinfra configurer pattern:
    - with_*() methods return self for chaining
    - done() returns parent builder

    Calling with_ipc() enables subprocess mode. Without it,
    the server runs uvicorn directly in the current process.

    Example:
        request_q, response_q = mp.Queue(), mp.Queue()

        server = (ServerBuilder("myapi")
            .subprocess
                .with_ipc(request_q, response_q)
                .with_log_file("/var/log/api.log")
                .with_auto_restart(enabled=True, max_restarts=10)
                .done()
            .build())
    """

    def __init__(self, parent: P) -> None:
        """
        Initialize configurer.

        Args:
            parent: Parent ServerBuilder instance
        """
        self._parent: P = parent

    def _ipc(self) -> IPCConfig:
        """The parent's IPC config, created on the first IPC setting.

        Lazy so that merely opening the facet leaves ``ApiConfig.ipc`` at
        ``None``, the documented value for a server without IPC.
        """
        if self._parent._api.ipc is None:
            self._parent._api.ipc = IPCConfig()
        return self._parent._api.ipc

    def with_ipc(
        self,
        request_q: mp.Queue[Any],
        response_q: mp.Queue[Any],
    ) -> Self:
        """
        Enable subprocess mode with queue-based IPC.

        Args:
            request_q: Queue for API -> main process requests
            response_q: Queue for main process -> API responses

        Returns:
            Self for method chaining
        """
        self._parent._request_q = request_q
        self._parent._response_q = response_q
        return self

    def with_log_file(self, path: str) -> Self:
        """
        Isolate subprocess logs to file.

        When set, all subprocess logging and stdout/stderr
        are redirected to this file.

        Args:
            path: Path to log file

        Returns:
            Self for method chaining
        """
        self._parent._api.log_file = path
        return self

    def with_poll_interval(self, interval: float) -> Self:
        """
        Set response queue polling interval.

        Lower values reduce latency but increase CPU usage.
        Default: 0.01 (10ms = 100 polls/second)

        Args:
            interval: Polling interval in seconds

        Returns:
            Self for method chaining
        """
        self._ipc().poll_interval = interval
        return self

    def with_response_timeout(self, timeout: float) -> Self:
        """
        Set default response timeout.

        Args:
            timeout: Timeout in seconds (default: 60.0)

        Returns:
            Self for method chaining
        """
        self._ipc().response_timeout = timeout
        return self

    def with_max_pending(self, max_pending: int) -> Self:
        """
        Set max pending requests before rejection.

        Prevents unbounded memory growth under load.

        Args:
            max_pending: Maximum pending requests (default: 100)

        Returns:
            Self for method chaining
        """
        self._ipc().max_pending = max_pending
        return self

    def with_health_reporting(self, enabled: bool = True) -> Self:
        """
        Enable/disable IPC health reporting in health endpoint.

        Args:
            enabled: Whether to include IPC stats in /_health

        Returns:
            Self for method chaining
        """
        self._ipc().enable_health_reporting = enabled
        return self

    def with_auto_restart(
        self,
        enabled: bool = True,
        delay: float = _API_DEFAULTS.restart_delay,
        max_restarts: int = _API_DEFAULTS.max_restarts,
    ) -> Self:
        """
        Configure automatic restart on crash.

        Args:
            enabled: Enable auto-restart (default: True)
            delay: Seconds to wait before restart (default: 1.0)
            max_restarts: Max restart attempts (default: 5, 0=unlimited)

        Returns:
            Self for method chaining
        """
        self._parent._api.auto_restart = enabled
        self._parent._api.restart_delay = delay
        self._parent._api.max_restarts = max_restarts
        return self

    def with_config(self, config: IPCConfig) -> Self:
        """Set entire IPC config at once."""
        self._parent._api.ipc = config
        return self

    def done(self) -> P:
        """
        Finish subprocess configuration and return to parent builder.

        Returns:
            Parent ServerBuilder instance for continued chaining
        """
        return self._parent
