"""
Ticker system for periodic task execution.

This module provides classes for implementing periodic task execution
with both scheduled and continuous modes. The system supports both
interval-based scheduling and continuous execution patterns.

The ticker system is designed for applications that need to perform
periodic tasks such as:
- Health checks and monitoring
- Data synchronization
- Periodic cleanup operations
- Status reporting
- Background processing

Key Features:
- Scheduled execution with precise intervals
- Continuous execution for high-frequency tasks
- Graceful stopping with cleanup
- Error handling and recovery
- Thread-safe operation
- Status monitoring and introspection

Example Usage:
    import logging

    lg = logging.getLogger(__name__)

    # Scheduled execution (every 5 seconds) with handler class
    class MyHandler(TickerHandler):
        def __init__(self):
            self.lg = logging.getLogger(__name__)

        def ticker_start(self, *args, **kwargs):
            self.lg.info("Ticker started")

        def ticker_tick(self):
            self.lg.info("Tick executed")

        def ticker_stop(self):
            self.lg.info("Ticker stopped")

    handler = MyHandler()
    ticker = Ticker(lg, handler, secs=5)
    ticker.run()

    # Simple callable (auto-wrapped)
    ticker = Ticker(lg, lambda: print("tick"), secs=5)
    ticker.run()

    # Continuous execution (no secs parameter)
    ticker = Ticker(lg, handler)
    ticker.run()
"""

import sched
import threading
import time
from collections.abc import Callable
from typing import Any


class TickerHandler:
    """
    Interface for objects that handle ticker events.

    Defines the methods that ticker-aware objects must implement
    to participate in the ticker system. All methods are optional
    and have default no-op implementations.

    This interface allows objects to participate in the ticker system
    by implementing the lifecycle methods they need. The ticker will
    call these methods at appropriate times during its execution.

    Example:
        import logging

        class DatabaseMonitor(TickerHandler):
            def __init__(self, db_connection):
                self.db = db_connection
                self.check_count = 0
                self.lg = logging.getLogger(__name__)

            def ticker_start(self, *args, **kwargs):
                self.lg.info("Starting database monitoring")
                self.check_count = 0

            def ticker_tick(self):
                self.check_count += 1
                if self.db.is_healthy():
                    self.lg.info(f"Database check #{self.check_count}: OK")
                else:
                    self.lg.warning(f"Database check #{self.check_count}: FAILED")

            def ticker_stop(self):
                self.lg.info(f"Database monitoring stopped after {self.check_count} checks")
    """

    def ticker_start(self, *args: Any, **kwargs: Any) -> None:
        """
        Called when the ticker starts.

        Args:
            *args: Positional arguments passed to ticker
            **kwargs: Keyword arguments passed to ticker
        """
        pass

    def ticker_before_first_tick(self, *args: Any, **kwargs: Any) -> None:
        """
        Called before the first tick execution.

        Args:
            *args: Positional arguments passed to ticker
            **kwargs: Keyword arguments passed to ticker
        """
        pass

    def ticker_tick(self) -> None:
        """
        Called on each tick execution.

        This method should contain the periodic work to be performed.
        """
        pass

    def ticker_stop(self) -> None:
        """
        Called when the ticker stops.

        This method is called when the ticker is stopped gracefully.
        """
        pass


class _CallableWrapper(TickerHandler):
    """
    Wrapper that adapts a plain callable to the TickerHandler interface.

    This allows users to pass simple functions or lambdas to Ticker
    without having to create a TickerHandler subclass.
    """

    def __init__(self, fn: Callable[[], None]) -> None:
        """
        Initialize the wrapper with a callable.

        Args:
            fn: Callable to execute on each tick
        """
        self._fn = fn

    def ticker_tick(self) -> None:
        """Execute the wrapped callable."""
        self._fn()


class Ticker:
    """
    Periodic task execution system.

    Provides both scheduled (with intervals) and continuous execution modes
    for periodic tasks. Can work with TickerHandler objects to execute
    periodic operations.

    The ticker supports two execution modes:
    - Scheduled: Uses sched.scheduler for interval-based execution
    - Continuous: Runs in a loop with no built-in stopping mechanism

    Thread safety: The ticker is not thread-safe by default. If you need
    thread safety, consider using locks or running in a separate thread.

    Example:
        import logging
        import threading

        lg = logging.getLogger(__name__)

        # Scheduled execution every 10 seconds
        class HealthChecker(TickerHandler):
            def __init__(self):
                self.lg = logging.getLogger(__name__)

            def ticker_tick(self):
                self.lg.info("Checking system health...")

        handler = HealthChecker()
        ticker = Ticker(lg, handler, secs=10)

        # Run in a separate thread
        thread = threading.Thread(target=ticker.run, daemon=True)
        thread.start()

        # Stop gracefully
        ticker.stop()

        # Or use a simple callable
        ticker = Ticker(lg, lambda: print("health check"), secs=10)
    """

    def __init__(
        self,
        lg: Any,
        handler: TickerHandler | Callable[[], None],
        secs: float | None = None,
        initial: bool = True,
    ) -> None:
        """
        Initialize the ticker.

        Args:
            lg: Logger instance for error logging
            handler: TickerHandler instance or callable to execute on each tick.
                     Plain callables are automatically wrapped in a TickerHandler.
            secs: Interval between ticks in seconds (None for continuous mode)
            initial: Whether to run tick immediately on start (default True).
                     If False, waits for first interval before firing.

        Raises:
            ValueError: If handler is None
        """
        if handler is None:
            raise ValueError("Handler cannot be None")

        # Auto-wrap plain callables in a TickerHandler
        if callable(handler) and not isinstance(handler, TickerHandler):
            handler = _CallableWrapper(handler)

        self._lg = lg
        self._handler = handler
        self._secs = secs
        self._initial = initial
        self._first = True
        self._running = False
        self._stop_event = threading.Event()
        self._sched = (
            sched.scheduler(time.time, time.sleep) if secs is not None else None
        )

    def run(self, *args: Any, **kwargs: Any) -> None:
        """
        Start the ticker execution.

        Args:
            *args: Positional arguments to pass to handler
            **kwargs: Keyword arguments to pass to handler

        Raises:
            RuntimeError: If ticker is already running

        Example:
            >>> import threading
            >>> from appinfra.time.ticker import Ticker, TickerHandler
            >>>
            >>> class MetricsCollector(TickerHandler):
            ...     def ticker_tick(self):
            ...         collect_and_report_metrics()
            >>>
            >>> ticker = Ticker(logger, MetricsCollector(), secs=30)
            >>>
            >>> # Run in background thread
            >>> thread = threading.Thread(target=ticker.run, daemon=True)
            >>> thread.start()
            >>>
            >>> # Later, stop gracefully
            >>> ticker.stop()
        """
        if self._running:
            raise RuntimeError("Ticker is already running")

        self._running = True
        self._stop_event.clear()

        try:
            self._handler.ticker_start(*args, **kwargs)
            self.run_started(*args, **kwargs)
        except Exception as e:
            self._running = False
            raise RuntimeError(f"Ticker execution failed: {e}") from e

    def run_started(self, *args: Any, **kwargs: Any) -> None:
        """
        Execute the ticker after startup.

        Chooses between scheduled and continuous execution based on configuration.

        Args:
            *args: Positional arguments to pass to handler
            **kwargs: Keyword arguments to pass to handler
        """
        kwargs = self._update_params_from_kwargs(kwargs)

        try:
            if self._sched is not None:
                # Scheduled execution mode
                self._tick_sched(*args, **kwargs)
                self._sched.run()
            else:
                # Continuous execution mode
                self._handler.ticker_before_first_tick(*args, **kwargs)
                while not self._stop_event.is_set():
                    try:
                        self._handler.ticker_tick()
                    except Exception:
                        # Log error but continue running unless it's a critical error
                        self._lg.exception("Error in ticker_tick")
        finally:
            self._running = False
            # Note: ticker_stop() is now called immediately in stop() method
            # to ensure cleanup logging happens during shutdown phase, not here

    def _tick_sched(self, *args: Any, **kwargs: Any) -> None:
        """
        Schedule the next tick in scheduled mode.

        Args:
            *args: Positional arguments to pass to handler
            **kwargs: Keyword arguments to pass to handler
        """
        if self._secs is None:
            raise RuntimeError("Cannot schedule tick without secs parameter")

        if not self._stop_event.is_set():
            # Schedule the next tick
            assert self._sched is not None  # Only called when sched mode is enabled
            self._sched.enter(self._secs, 1, self._tick_sched, args, kwargs)

            if self._first:
                self._first = False
                try:
                    self._handler.ticker_before_first_tick(*args, **kwargs)
                except Exception:
                    self._lg.exception("Error in ticker_before_first_tick")
                if not self._initial:
                    return  # Skip immediate fire, wait for first interval

            try:
                self._handler.ticker_tick()
            except Exception:
                self._lg.exception("Error in ticker_tick")

    def _update_params_from_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Update ticker parameters from keyword arguments.

        Args:
            kwargs: Keyword arguments dictionary

        Returns:
            dict: Updated keyword arguments
        """
        # Fix: Check for the correct key names
        if "ticker_secs" in kwargs:
            self._secs = kwargs["ticker_secs"]
            del kwargs["ticker_secs"]
        if "ticker_initial" in kwargs:
            self._initial = kwargs["ticker_initial"]
            del kwargs["ticker_initial"]
        return kwargs

    def stop(self) -> None:
        """
        Stop the ticker gracefully.

        This method signals the ticker to stop and calls the handler's
        ticker_stop method immediately. The ticker will stop after the current
        tick completes.
        """
        if self._running:
            self._stop_event.set()
            # For scheduled mode, we need to cancel pending events
            if self._sched is not None:
                # Cancel all pending events
                for event in self._sched.queue:
                    self._sched.cancel(event)

            # Call ticker_stop handler immediately so cleanup logging
            # happens during the shutdown phase, not in finally block
            try:
                self._handler.ticker_stop()
            except Exception:
                # Log error but continue with stop
                self._lg.exception("Error in ticker_stop callback")

    def is_running(self) -> bool:
        """
        Check if the ticker is currently running.

        Returns:
            bool: True if the ticker is running, False otherwise
        """
        return self._running

    def get_status(self) -> dict:
        """
        Get the current status of the ticker.

        Returns:
            dict: Status information including running state, mode, and interval
        """
        return {
            "running": self._running,
            "mode": "scheduled" if self._sched is not None else "continuous",
            "interval": self._secs,
            "first_tick": self._first,
            "stop_requested": self._stop_event.is_set(),
        }
