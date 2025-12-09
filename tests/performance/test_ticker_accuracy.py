"""Performance tests for ticker interval accuracy."""

import threading
import time

import pytest

from appinfra.time.ticker import Ticker, TickerHandler


class PerfTestHandler(TickerHandler):
    """Test handler that records tick times."""

    def __init__(self):
        self.ticks = []

    def ticker_start(self, *args, **kwargs):
        pass

    def ticker_tick(self):
        self.ticks.append(time.monotonic())

    def ticker_stop(self):
        pass


@pytest.mark.performance
@pytest.mark.slow
class TestTickerAccuracy:
    def test_interval_timing_accuracy(self):
        """Measure ticker interval deviation from expected 0.1s."""
        import logging

        lg = logging.getLogger(__name__)
        handler = PerfTestHandler()
        ticker = Ticker(lg, handler, secs=0.1)

        # Run ticker for ~1 second (expect ~10 ticks)
        thread = threading.Thread(target=ticker.run, daemon=True)
        thread.start()
        time.sleep(1.0)
        ticker.stop()
        thread.join(timeout=1.0)

        # Analyze: Calculate interval deviations
        ticks = handler.ticks
        if len(ticks) < 3:
            pytest.skip("Not enough ticks collected")

        intervals = [ticks[i + 1] - ticks[i] for i in range(len(ticks) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        max_deviation = max(abs(interval - 0.1) for interval in intervals)

        # Assert: Average close to 0.1s, max deviation < 100ms
        assert abs(avg_interval - 0.1) < 0.05, (
            f"Interval average off: {avg_interval:.3f}s vs 0.1s expected"
        )
        assert max_deviation < 0.1, (
            f"Interval deviation too high: {max_deviation * 1000:.1f}ms > 100ms"
        )

        print(
            f"\nTicker accuracy: avg={avg_interval:.3f}s, "
            f"max_dev={max_deviation * 1000:.1f}ms"
        )
