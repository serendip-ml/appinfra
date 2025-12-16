"""Subprocess management with auto-restart."""

from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("fastapi.subprocess")


@dataclass
class SubprocessState:
    """Subprocess lifecycle state."""

    process: mp.Process | None = None
    restart_count: int = 0
    last_restart: float = 0.0
    stop_requested: bool = False


class SubprocessManager:
    """
    Manages uvicorn subprocess lifecycle with auto-restart.

    Features:
    - Process spawning with proper argument passing
    - Graceful shutdown with fallback kill (terminate -> join -> kill)
    - Auto-restart on crash (configurable)
    - Process health monitoring via background thread

    Example:
        manager = SubprocessManager(
            target=run_uvicorn,
            args=(request_q, response_q, config),
            auto_restart=True,
            max_restarts=5,
        )
        proc = manager.start()
        # ... later ...
        manager.stop()
    """

    def __init__(
        self,
        target: Callable[..., Any],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        shutdown_timeout: float = 5.0,
        auto_restart: bool = True,
        restart_delay: float = 1.0,
        max_restarts: int = 5,
    ) -> None:
        """
        Initialize subprocess manager.

        Args:
            target: Callable to run in subprocess (e.g., run_uvicorn)
            args: Positional arguments for target
            kwargs: Keyword arguments for target
            shutdown_timeout: Seconds to wait for graceful shutdown before kill
            auto_restart: Enable automatic restart on crash (default: True)
            restart_delay: Seconds to wait before restart (default: 1.0)
            max_restarts: Max restart attempts before giving up (default: 5).
                Set to 0 for unlimited restarts.
        """
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self._shutdown_timeout = shutdown_timeout
        self._auto_restart = auto_restart
        self._restart_delay = restart_delay
        self._max_restarts = max_restarts

        self._state = SubprocessState()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def process(self) -> mp.Process | None:
        """Current process instance."""
        return self._state.process

    @property
    def pid(self) -> int | None:
        """Process ID if running."""
        proc = self._state.process
        return proc.pid if proc else None

    @property
    def restart_count(self) -> int:
        """Number of restarts since start()."""
        return self._state.restart_count

    def is_alive(self) -> bool:
        """Check if process is running."""
        proc = self._state.process
        return proc is not None and proc.is_alive()

    def start(self) -> mp.Process:
        """
        Start the subprocess.

        Returns:
            The Process object

        Raises:
            RuntimeError: If process is already running
        """
        with self._lock:
            if self.is_alive():
                raise RuntimeError("Process already running")

            self._state.stop_requested = False
            self._state.restart_count = 0
            return self._spawn_process()

    def stop(self) -> None:
        """
        Gracefully stop the subprocess.

        Uses terminate -> join(timeout) -> kill pattern.
        """
        with self._lock:
            self._state.stop_requested = True

        # Stop monitor thread first
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        self._monitor_thread = None

        # Stop process
        proc = self._state.process
        if proc:
            self._graceful_shutdown(proc)
            self._state.process = None

    def _spawn_process(self) -> mp.Process:
        """Spawn a new subprocess."""
        proc = mp.Process(
            target=self._target,
            args=self._args,
            kwargs=self._kwargs,
            daemon=True,
        )
        proc.start()
        self._state.process = proc
        self._state.last_restart = time.time()

        logger.info(f"Subprocess started (pid={proc.pid})")

        # Start monitor thread if auto-restart enabled
        if self._auto_restart and self._monitor_thread is None:
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="subprocess-monitor",
            )
            self._monitor_thread.start()

        return proc

    def _monitor_loop(self) -> None:
        """Monitor subprocess and restart on crash."""
        while not self._state.stop_requested:
            proc = self._state.process
            if proc is None:
                break

            proc.join(timeout=1.0)

            if proc.is_alive():
                continue
            if self._state.stop_requested:
                break
            if not self._handle_process_exit(proc.exitcode):
                break

    def _handle_process_exit(self, exit_code: int | None) -> bool:
        """Handle subprocess exit, return True to continue monitoring (restart)."""
        # Exit code 0 = clean shutdown (e.g., SIGINT), don't restart
        if exit_code == 0:
            logger.info("subprocess exited cleanly (code=0), not restarting")
            return False

        logger.warning(
            f"Subprocess crashed (code={exit_code}, restarts={self._state.restart_count})"
        )

        if self._should_restart():
            self._do_restart()
            return True

        logger.error(f"Max restarts exceeded ({self._max_restarts}), giving up")
        return False

    def _should_restart(self) -> bool:
        """Check if restart should be attempted."""
        if self._max_restarts == 0:
            return True  # Unlimited restarts
        return self._state.restart_count < self._max_restarts

    def _do_restart(self) -> None:
        """Perform restart with delay."""
        self._state.restart_count += 1

        max_str = str(self._max_restarts) if self._max_restarts > 0 else "unlimited"
        logger.info(
            f"Restarting subprocess "
            f"(attempt {self._state.restart_count}/{max_str}, "
            f"delay={self._restart_delay}s)"
        )

        time.sleep(self._restart_delay)

        if not self._state.stop_requested:
            with self._lock:
                self._spawn_process()

    def _graceful_shutdown(self, proc: mp.Process) -> None:
        """
        Graceful shutdown: terminate -> join(timeout) -> kill.

        This pattern ensures cleanup even if the process is hung.
        """
        logger.debug("stopping subprocess...")

        # Send SIGTERM
        proc.terminate()

        # Wait for graceful exit
        proc.join(timeout=self._shutdown_timeout)

        # Force kill if still alive
        if proc.is_alive():
            logger.warning(
                f"Subprocess did not terminate within {self._shutdown_timeout}s, "
                "sending SIGKILL"
            )
            proc.kill()
            proc.join()

        logger.info("subprocess stopped")
