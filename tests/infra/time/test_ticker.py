"""
Comprehensive tests for ticker system.

Tests the Ticker and TickerHandler functionality including:
- Ticker initialization with validation
- Scheduled execution mode with intervals
- Continuous execution mode
- Lifecycle methods (start, tick, stop)
- Graceful stopping and cleanup
- Status monitoring
- Error handling
"""

import logging
import threading
import time
from unittest.mock import Mock

import pytest

from appinfra.time.ticker import Ticker, TickerHandler

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock logger for tests."""
    logger = Mock(spec=logging.Logger)
    logger.exception = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    return logger


@pytest.fixture
def mock_handler():
    """Create mock ticker handler."""
    handler = Mock(spec=TickerHandler)
    handler.ticker_start = Mock()
    handler.ticker_before_first_tick = Mock()
    handler.ticker_tick = Mock()
    handler.ticker_stop = Mock()
    return handler


@pytest.fixture
def simple_handler():
    """Create simple TickerHandler implementation."""

    class SimpleHandler(TickerHandler):
        def __init__(self):
            self.tick_count = 0
            self.started = False
            self.stopped = False

        def ticker_start(self, *args, **kwargs):
            self.started = True

        def ticker_tick(self):
            self.tick_count += 1

        def ticker_stop(self):
            self.stopped = True

    return SimpleHandler()


# =============================================================================
# Test TickerHandler Interface
# =============================================================================


@pytest.mark.unit
class TestTickerHandler:
    """Test TickerHandler interface."""

    def test_default_ticker_start_is_noop(self):
        """Test default ticker_start does nothing."""
        handler = TickerHandler()
        # Should not raise
        handler.ticker_start()

    def test_default_ticker_before_first_tick_is_noop(self):
        """Test default ticker_before_first_tick does nothing."""
        handler = TickerHandler()
        # Should not raise
        handler.ticker_before_first_tick()

    def test_default_ticker_tick_is_noop(self):
        """Test default ticker_tick does nothing."""
        handler = TickerHandler()
        # Should not raise
        handler.ticker_tick()

    def test_default_ticker_stop_is_noop(self):
        """Test default ticker_stop does nothing."""
        handler = TickerHandler()
        # Should not raise
        handler.ticker_stop()

    def test_custom_handler_implements_all_methods(self, mock_logger, simple_handler):
        """Test custom handler can override all methods."""
        simple_handler.ticker_start()
        simple_handler.ticker_tick()
        simple_handler.ticker_stop()

        assert simple_handler.started is True
        assert simple_handler.tick_count == 1
        assert simple_handler.stopped is True


# =============================================================================
# Test Ticker Initialization
# =============================================================================


@pytest.mark.unit
class TestTickerInitialization:
    """Test Ticker initialization."""

    def test_init_with_valid_handler_scheduled_mode(self, mock_logger, mock_handler):
        """Test initialization with handler in scheduled mode."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        assert ticker._handler == mock_handler
        assert ticker._secs == 1.0
        assert ticker._sched is not None
        assert ticker._running is False

    def test_init_with_valid_handler_continuous_mode(self, mock_logger, mock_handler):
        """Test initialization with handler in continuous mode."""
        ticker = Ticker(mock_logger, mock_handler)
        assert ticker._handler == mock_handler
        assert ticker._secs is None
        assert ticker._sched is None
        assert ticker._running is False

    def test_init_with_none_handler_for_iterator_mode(self, mock_logger):
        """Test initialization with None handler is allowed for iterator mode."""
        ticker = Ticker(mock_logger, secs=1.0)
        assert ticker._handler is None
        assert ticker._secs == 1.0

    def test_run_with_none_handler_raises_error(self, mock_logger):
        """Test run() with None handler raises ValueError."""
        ticker = Ticker(mock_logger, secs=1.0)
        with pytest.raises(ValueError, match="Handler required for run\\(\\) mode"):
            ticker.run()

    def test_init_creates_stop_event(self, mock_logger, mock_handler):
        """Test initialization creates stop event."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        assert isinstance(ticker._stop_event, threading.Event)
        assert not ticker._stop_event.is_set()

    def test_init_sets_first_flag(self, mock_logger, mock_handler):
        """Test initialization sets first tick flag."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        assert ticker._first is True

    def test_init_with_initial_parameter(self, mock_logger, mock_handler):
        """Test initialization with initial parameter."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0, initial=False)
        assert ticker._initial is False

    def test_initial_false_skips_immediate_tick(self, mock_logger):
        """Test initial=False skips the immediate tick and waits for interval."""
        tick_times = []

        class TimingHandler(TickerHandler):
            def ticker_tick(self):
                tick_times.append(time.time())

        start_time = time.time()
        ticker = Ticker(mock_logger, TimingHandler(), secs=0.1, initial=False)

        thread = threading.Thread(target=ticker.run, daemon=True)
        thread.start()
        time.sleep(0.15)  # Wait for first interval to pass
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have at least one tick after waiting
        assert len(tick_times) >= 1
        # First tick should be delayed by approximately secs interval
        assert tick_times[0] - start_time >= 0.08  # Allow some tolerance

    def test_initial_true_fires_immediately(self, mock_logger):
        """Test initial=True (default) fires tick immediately on start."""
        tick_times = []

        class TimingHandler(TickerHandler):
            def ticker_tick(self):
                tick_times.append(time.time())

        start_time = time.time()
        ticker = Ticker(mock_logger, TimingHandler(), secs=0.1, initial=True)

        thread = threading.Thread(target=ticker.run, daemon=True)
        thread.start()
        time.sleep(0.05)  # Short wait - tick should already have fired
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have at least one tick immediately
        assert len(tick_times) >= 1
        # First tick should be almost immediate (within 50ms of start)
        assert tick_times[0] - start_time < 0.05


# =============================================================================
# Test Scheduled Execution Mode
# =============================================================================


@pytest.mark.unit
class TestScheduledMode:
    """Test scheduled execution mode."""

    def test_scheduled_mode_calls_ticker_start(self, mock_logger, mock_handler):
        """Test scheduled mode calls ticker_start."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        # Run in thread and stop quickly
        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_start.assert_called_once()

    def test_scheduled_mode_calls_before_first_tick(self, mock_logger, mock_handler):
        """Test scheduled mode calls ticker_before_first_tick."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.15)  # Wait for first tick
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_before_first_tick.assert_called_once()

    def test_scheduled_mode_executes_multiple_ticks(self, mock_logger, simple_handler):
        """Test scheduled mode executes multiple ticks."""
        ticker = Ticker(mock_logger, simple_handler, secs=0.05)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.25)  # Allow multiple ticks
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have executed multiple ticks
        assert simple_handler.tick_count >= 2

    def test_scheduled_mode_calls_ticker_stop(self, mock_logger, mock_handler):
        """Test scheduled mode calls ticker_stop on cleanup."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_stop.assert_called_once()

    def test_scheduled_mode_handles_ticker_before_first_tick_error(
        self, mock_logger, mock_handler
    ):
        """Test scheduled mode handles errors in ticker_before_first_tick."""
        mock_handler.ticker_before_first_tick.side_effect = Exception(
            "before first tick error"
        )
        ticker = Ticker(mock_logger, mock_handler, secs=0.05)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.15)  # Wait for first tick and error
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have called ticker_before_first_tick once
        mock_handler.ticker_before_first_tick.assert_called_once()
        # Should have logged the exception
        mock_logger.exception.assert_called()
        # Ticker should continue and call ticker_tick despite error
        assert mock_handler.ticker_tick.call_count >= 1

    def test_scheduled_mode_handles_ticker_tick_error(self, mock_logger, mock_handler):
        """Test scheduled mode handles errors in ticker_tick."""
        mock_handler.ticker_tick.side_effect = Exception("tick error")
        ticker = Ticker(mock_logger, mock_handler, secs=0.05)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.15)  # Allow multiple attempts
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have called ticker_tick multiple times despite errors
        assert mock_handler.ticker_tick.call_count >= 1

    def test_scheduled_mode_stops_gracefully(self, mock_logger, simple_handler):
        """Test scheduled mode stops gracefully."""
        ticker = Ticker(mock_logger, simple_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)

        initial_count = simple_handler.tick_count
        ticker.stop()
        thread.join(timeout=1.0)

        # Should stop cleanly
        assert simple_handler.stopped is True
        assert not ticker.is_running()


# =============================================================================
# Test Continuous Execution Mode
# =============================================================================


@pytest.mark.unit
class TestContinuousMode:
    """Test continuous execution mode."""

    def test_continuous_mode_calls_ticker_start(self, mock_logger, mock_handler):
        """Test continuous mode calls ticker_start."""
        ticker = Ticker(mock_logger, mock_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.01)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_start.assert_called_once()

    def test_continuous_mode_calls_before_first_tick(self, mock_logger, mock_handler):
        """Test continuous mode calls ticker_before_first_tick."""
        ticker = Ticker(mock_logger, mock_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.01)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_before_first_tick.assert_called_once()

    def test_continuous_mode_executes_many_ticks(self, mock_logger, simple_handler):
        """Test continuous mode executes many ticks rapidly."""
        ticker = Ticker(mock_logger, simple_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.1)  # Short time but should execute many ticks
        ticker.stop()
        thread.join(timeout=1.0)

        # Continuous mode should execute many times
        assert simple_handler.tick_count > 10

    def test_continuous_mode_stops_on_stop_event(self, mock_logger, simple_handler):
        """Test continuous mode stops when stop event is set."""
        ticker = Ticker(mock_logger, simple_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have stopped
        assert ticker._stop_event.is_set()
        assert simple_handler.stopped is True

    def test_continuous_mode_handles_ticker_tick_error(self, mock_logger, mock_handler):
        """Test continuous mode handles errors in ticker_tick."""
        # First few calls raise error, then we stop
        call_count = [0]

        def side_effect():
            call_count[0] += 1
            if call_count[0] < 5:
                raise Exception("tick error")

        mock_handler.ticker_tick.side_effect = side_effect
        ticker = Ticker(mock_logger, mock_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.01)
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have called ticker_tick multiple times despite errors
        assert mock_handler.ticker_tick.call_count >= 1

    def test_continuous_mode_calls_ticker_stop(self, mock_logger, mock_handler):
        """Test continuous mode calls ticker_stop on cleanup."""
        ticker = Ticker(mock_logger, mock_handler)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.01)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_stop.assert_called_once()


# =============================================================================
# Test Ticker Control Methods
# =============================================================================


@pytest.mark.unit
class TestTickerControl:
    """Test ticker control methods."""

    def test_is_running_returns_false_initially(self, mock_logger, mock_handler):
        """Test is_running returns False initially."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        assert ticker.is_running() is False

    def test_is_running_returns_true_while_running(self, mock_logger, mock_handler):
        """Test is_running returns True while running."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)

        assert ticker.is_running() is True

        ticker.stop()
        thread.join(timeout=1.0)

    def test_is_running_returns_false_after_stop(self, mock_logger, mock_handler):
        """Test is_running returns False after stopping."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        assert ticker.is_running() is False

    def test_get_status_returns_dict(self, mock_logger, mock_handler):
        """Test get_status returns status dictionary."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        status = ticker.get_status()

        assert isinstance(status, dict)
        assert "running" in status
        assert "mode" in status
        assert "interval" in status
        assert "first_tick" in status
        assert "stop_requested" in status

    def test_get_status_shows_scheduled_mode(self, mock_logger, mock_handler):
        """Test get_status shows scheduled mode."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)
        status = ticker.get_status()

        assert status["mode"] == "scheduled"
        assert status["interval"] == 1.0

    def test_get_status_shows_continuous_mode(self, mock_logger, mock_handler):
        """Test get_status shows continuous mode."""
        ticker = Ticker(mock_logger, mock_handler)
        status = ticker.get_status()

        assert status["mode"] == "continuous"
        assert status["interval"] is None

    def test_get_status_shows_running_state(self, mock_logger, mock_handler):
        """Test get_status shows running state."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        # Initially not running
        status = ticker.get_status()
        assert status["running"] is False

        # Start ticker
        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)

        # Should be running
        status = ticker.get_status()
        assert status["running"] is True

        ticker.stop()
        thread.join(timeout=1.0)

    def test_run_raises_if_already_running(self, mock_logger, mock_handler):
        """Test run raises RuntimeError if already running."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)

        # Try to run again
        with pytest.raises(RuntimeError, match="already running"):
            ticker.run()

        ticker.stop()
        thread.join(timeout=1.0)

    def test_stop_cancels_scheduled_events(self, mock_logger, mock_handler):
        """Test stop cancels pending scheduled events."""
        ticker = Ticker(mock_logger, mock_handler, secs=10.0)  # Long interval

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)

        # Stop before next tick
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have cancelled pending events
        assert ticker._sched.queue == []


# =============================================================================
# Test Integration Scenarios
# =============================================================================


@pytest.mark.integration
class TestIntegrationScenarios:
    """Test real-world ticker scenarios."""

    def test_ticker_with_args_and_kwargs(self, mock_logger, mock_handler):
        """Test ticker passes args and kwargs to handler."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run("arg1", "arg2", key="value")

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        mock_handler.ticker_start.assert_called_once_with("arg1", "arg2", key="value")

    def test_update_params_from_kwargs(self, mock_logger, mock_handler):
        """Test updating ticker params from kwargs."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)

        # Update params
        kwargs = {"ticker_secs": 2.0, "ticker_initial": False, "other": "value"}
        result = ticker._update_params_from_kwargs(kwargs)

        assert ticker._secs == 2.0
        assert ticker._initial is False
        assert "ticker_secs" not in result
        assert "ticker_initial" not in result
        assert result["other"] == "value"

    def test_ticker_handles_handler_start_error(self, mock_logger, mock_handler):
        """Test ticker handles error in ticker_start."""
        mock_handler.ticker_start.side_effect = Exception("start error")
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        with pytest.raises(RuntimeError, match="Ticker execution failed"):
            ticker.run()

        # Should not be running after error
        assert not ticker.is_running()


# =============================================================================
# Test Callable Wrapper
# =============================================================================


@pytest.mark.unit
class TestCallableWrapper:
    """Test automatic wrapping of plain callables."""

    def test_callable_is_wrapped_in_handler(self, mock_logger):
        """Test that a plain callable is wrapped in a TickerHandler."""
        call_count = [0]

        def my_tick():
            call_count[0] += 1

        ticker = Ticker(mock_logger, my_tick, secs=0.05)

        # Handler should be wrapped
        from appinfra.time.ticker import _CallableWrapper

        assert isinstance(ticker._handler, _CallableWrapper)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.1)
        ticker.stop()
        thread.join(timeout=1.0)

        # Should have executed the callable
        assert call_count[0] >= 1

    def test_lambda_is_wrapped(self, mock_logger):
        """Test that a lambda is wrapped in a TickerHandler."""
        results = []

        ticker = Ticker(mock_logger, lambda: results.append("tick"), secs=0.05)

        from appinfra.time.ticker import _CallableWrapper

        assert isinstance(ticker._handler, _CallableWrapper)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.1)
        ticker.stop()
        thread.join(timeout=1.0)

        assert len(results) >= 1
        assert results[0] == "tick"

    def test_callable_in_continuous_mode(self, mock_logger):
        """Test callable works in continuous mode."""
        call_count = [0]

        def my_tick():
            call_count[0] += 1

        ticker = Ticker(mock_logger, my_tick)  # No secs = continuous

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        thread.join(timeout=1.0)

        # Continuous mode should execute many times
        assert call_count[0] > 10

    def test_handler_instance_not_wrapped(self, mock_logger, mock_handler):
        """Test that TickerHandler instances are not wrapped."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)

        # Should use handler directly
        assert ticker._handler is mock_handler


# =============================================================================
# Test Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_update_params_from_kwargs_unit(self, mock_logger, mock_handler):
        """Test updating ticker params from kwargs (unit test version)."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)

        # Update params
        kwargs = {"ticker_secs": 2.0, "ticker_initial": False, "other": "value"}
        result = ticker._update_params_from_kwargs(kwargs)

        assert ticker._secs == 2.0
        assert ticker._initial is False
        assert "ticker_secs" not in result
        assert "ticker_initial" not in result
        assert result["other"] == "value"

    def test_ticker_handles_handler_start_error_unit(self, mock_logger, mock_handler):
        """Test ticker handles error in ticker_start (unit test version)."""
        mock_handler.ticker_start.side_effect = Exception("start error")
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        with pytest.raises(RuntimeError, match="Ticker execution failed"):
            ticker.run()

        # Should not be running after error
        assert not ticker.is_running()

    def test_ticker_with_zero_interval(self, mock_logger, simple_handler):
        """Test ticker with zero second interval."""
        ticker = Ticker(mock_logger, simple_handler, secs=0.0)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.1)
        ticker.stop()
        thread.join(timeout=1.0)

        # Should execute multiple times even with 0 interval
        assert simple_handler.tick_count >= 1

    def test_ticker_stop_when_not_running(self, mock_logger, mock_handler):
        """Test stop when ticker is not running."""
        ticker = Ticker(mock_logger, mock_handler, secs=1.0)

        # Should not raise
        ticker.stop()

        # Stop event should be set (allows stopping iterator mode before iteration)
        assert ticker._stop_event.is_set()

    def test_scheduled_tick_without_secs_raises_error(self, mock_logger, mock_handler):
        """Test _tick_sched raises error without secs."""
        ticker = Ticker(mock_logger, mock_handler)  # No secs
        ticker._secs = None

        with pytest.raises(RuntimeError, match="Cannot schedule tick without secs"):
            ticker._tick_sched()

    def test_ticker_stop_handles_handler_stop_error(self, mock_logger, mock_handler):
        """Test ticker handles error in ticker_stop gracefully."""
        mock_handler.ticker_stop.side_effect = Exception("stop error")
        ticker = Ticker(mock_logger, mock_handler, secs=0.1)

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker.stop()
        # Should not raise, error is caught
        thread.join(timeout=1.0)

    def test_first_flag_reset_after_first_tick(self, mock_logger, mock_handler):
        """Test first flag is reset after first tick."""
        ticker = Ticker(mock_logger, mock_handler, secs=0.05)
        assert ticker._first is True

        def run_and_stop():
            ticker.run()

        thread = threading.Thread(target=run_and_stop, daemon=True)
        thread.start()
        time.sleep(0.1)  # Wait for first tick
        ticker.stop()
        thread.join(timeout=1.0)

        assert ticker._first is False


# =============================================================================
# Test Iterator and Context Manager Support
# =============================================================================


@pytest.mark.unit
class TestTickerIterator:
    """Test Ticker iterator functionality."""

    def test_yields_tick_count(self, mock_logger):
        """Verify ticker yields incrementing tick numbers."""
        ticks = []
        with Ticker(mock_logger, secs=0.01) as t:
            for tick in t:
                ticks.append(tick)
                if tick >= 2:
                    t.stop()
        assert ticks == [0, 1, 2]

    def test_initial_false_skips_first_tick(self, mock_logger):
        """Verify initial=False waits before first tick."""
        ticks = []
        start = time.time()
        with Ticker(mock_logger, secs=0.05, initial=False) as t:
            for tick in t:
                ticks.append((tick, time.time() - start))
                if tick >= 0:
                    t.stop()
        # First tick should be delayed by approximately secs
        assert len(ticks) == 1
        assert ticks[0][0] == 0
        assert ticks[0][1] >= 0.04  # Allow some tolerance

    def test_initial_true_fires_immediately(self, mock_logger):
        """Verify initial=True (default) fires tick immediately."""
        ticks = []
        start = time.time()
        with Ticker(mock_logger, secs=1.0) as t:  # Long interval
            for tick in t:
                ticks.append((tick, time.time() - start))
                t.stop()
        # First tick should be almost immediate
        assert len(ticks) == 1
        assert ticks[0][0] == 0
        assert ticks[0][1] < 0.05  # Should fire within 50ms

    def test_works_without_context_manager(self, mock_logger):
        """Verify iteration works without with statement."""
        ticks = []
        ticker = Ticker(mock_logger, secs=0.01)
        for tick in ticker:
            ticks.append(tick)
            if tick >= 2:
                ticker.stop()
        assert ticks == [0, 1, 2]

    def test_iter_requires_secs(self, mock_logger):
        """Test iterator mode requires secs parameter."""
        ticker = Ticker(mock_logger)  # No secs
        with pytest.raises(ValueError, match="secs parameter required"):
            for _ in ticker:
                pass

    def test_stop_before_iteration(self, mock_logger):
        """Test stopping ticker before iteration starts."""
        ticker = Ticker(mock_logger, secs=0.01)
        ticker.stop()

        ticks = []
        for tick in ticker:
            ticks.append(tick)
        # Should not yield anything since stopped before iteration
        assert ticks == []


@pytest.mark.unit
class TestTickerContextManager:
    """Test Ticker context manager functionality."""

    def test_context_manager_installs_signal_handlers(self, mock_logger):
        """Verify context manager installs signal handlers."""
        import signal as sig

        original_sigterm = sig.getsignal(sig.SIGTERM)
        original_sigint = sig.getsignal(sig.SIGINT)

        with Ticker(mock_logger, secs=1.0) as ticker:
            # Signal handlers should be installed
            current_sigterm = sig.getsignal(sig.SIGTERM)
            current_sigint = sig.getsignal(sig.SIGINT)
            assert current_sigterm != original_sigterm
            assert current_sigint != original_sigint
            ticker.stop()

        # Signal handlers should be restored
        assert sig.getsignal(sig.SIGTERM) == original_sigterm
        assert sig.getsignal(sig.SIGINT) == original_sigint

    def test_context_manager_restores_handlers_on_exception(self, mock_logger):
        """Verify signal handlers are restored even on exception."""
        import signal as sig

        original_sigterm = sig.getsignal(sig.SIGTERM)

        try:
            with Ticker(mock_logger, secs=1.0):
                raise ValueError("test error")
        except ValueError:
            pass

        # Signal handlers should be restored
        assert sig.getsignal(sig.SIGTERM) == original_sigterm

    def test_signal_handler_sets_stop_event(self, mock_logger):
        """Verify signal handler sets stop event when called."""
        ticker = Ticker(mock_logger, secs=1.0)

        with ticker:
            # Manually invoke the signal handler (simulating signal delivery)
            ticker._handle_iter_signal(15, None)  # 15 = SIGTERM

            # Stop event should be set
            assert ticker._stop_event.is_set()

        # Logger should have logged the signal
        mock_logger.debug.assert_called()

    def test_nested_context_managers(self, mock_logger):
        """Test nested ticker context managers restore handlers correctly."""
        import signal as sig

        original_sigterm = sig.getsignal(sig.SIGTERM)

        with Ticker(mock_logger, secs=1.0) as outer:
            outer_handler = sig.getsignal(sig.SIGTERM)

            with Ticker(mock_logger, secs=1.0) as inner:
                inner_handler = sig.getsignal(sig.SIGTERM)
                # Inner should have its own handler
                assert inner_handler != outer_handler
                inner.stop()

            # After inner exits, outer's handler should be restored
            assert sig.getsignal(sig.SIGTERM) == outer_handler
            outer.stop()

        # After outer exits, original handler should be restored
        assert sig.getsignal(sig.SIGTERM) == original_sigterm


@pytest.mark.integration
class TestTickerIteratorIntegration:
    """Integration tests for Ticker iterator with SubprocessContext pattern."""

    def test_multiple_ticks_with_timing(self, mock_logger):
        """Test ticker yields at correct intervals."""
        ticks = []
        start = time.time()

        with Ticker(mock_logger, secs=0.05) as t:
            for tick in t:
                ticks.append((tick, time.time() - start))
                if tick >= 2:
                    t.stop()

        # Should have 3 ticks (0, 1, 2)
        assert len(ticks) == 3

        # First tick should be immediate
        assert ticks[0][1] < 0.02

        # Subsequent ticks should be spaced by ~0.05s
        assert 0.04 < ticks[1][1] - ticks[0][1] < 0.08
        assert 0.04 < ticks[2][1] - ticks[1][1] < 0.08

    def test_callback_and_iterator_are_separate_modes(self, mock_logger):
        """Test that callback mode and iterator mode are independent."""
        # Callback mode
        call_count = [0]
        ticker1 = Ticker(
            mock_logger, lambda: call_count.__setitem__(0, call_count[0] + 1), secs=0.01
        )
        thread = threading.Thread(target=ticker1.run, daemon=True)
        thread.start()
        time.sleep(0.05)
        ticker1.stop()
        thread.join(timeout=1.0)
        assert call_count[0] >= 1

        # Iterator mode (no handler)
        iter_count = 0
        ticker2 = Ticker(mock_logger, secs=0.01)
        for tick in ticker2:
            iter_count += 1
            if tick >= 2:
                ticker2.stop()
        assert iter_count == 3
