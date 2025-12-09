"""
Tests for rate limiting functionality.

Tests key rate limiter features including:
- Rate limiter initialization
- Rate limiting behavior
- Waiting between operations
"""

import time
from unittest.mock import Mock

import pytest

from appinfra.rate_limit import RateLimiter

# =============================================================================
# Test RateLimiter Initialization
# =============================================================================


@pytest.mark.unit
class TestRateLimiterInitialization:
    """Test RateLimiter initialization."""

    def test_init_with_per_minute(self):
        """Test initialization with per_minute parameter."""
        limiter = RateLimiter(per_minute=60)
        assert limiter.per_minute == 60
        assert limiter.last_t is None

    def test_init_with_logger(self):
        """Test initialization with logger."""
        mock_logger = Mock()
        limiter = RateLimiter(per_minute=60, lg=mock_logger)
        assert limiter._lg is mock_logger

    def test_init_without_logger(self):
        """Test initialization without logger."""
        limiter = RateLimiter(per_minute=60)
        assert limiter._lg is None


# =============================================================================
# Test RateLimiter next() Method
# =============================================================================


@pytest.mark.unit
class TestRateLimiterNext:
    """Test RateLimiter next() method."""

    def test_first_call_no_wait(self):
        """Test first call to next() doesn't wait."""
        limiter = RateLimiter(per_minute=60)
        wait = limiter.next()
        assert wait == 0
        assert limiter.last_t is not None

    def test_rapid_calls_cause_waiting(self):
        """Test rapid calls cause waiting."""
        limiter = RateLimiter(per_minute=120)  # 2 per second

        # First call
        limiter.next()

        # Second call should wait
        start = time.monotonic()
        wait = limiter.next()
        elapsed = time.monotonic() - start

        # Should have waited approximately the delay amount
        assert wait > 0
        assert elapsed >= wait * 0.9  # Allow 10% tolerance

    def test_respect_max_ticks_false_no_sleep(self):
        """Test respect_max_ticks=False doesn't sleep."""
        limiter = RateLimiter(per_minute=120)

        # First call
        limiter.next()

        # Second call with respect_max_ticks=False should not sleep
        start = time.monotonic()
        wait = limiter.next(respect_max_ticks=False)
        elapsed = time.monotonic() - start

        # Should calculate wait but not actually sleep
        assert wait > 0
        assert elapsed < 0.01  # Should be very quick

    def test_sufficient_delay_no_wait(self):
        """Test sufficient delay between calls doesn't cause waiting."""
        limiter = RateLimiter(per_minute=60)

        # First call
        limiter.next()

        # Wait for the rate limit delay
        time.sleep(1.1)  # Slightly more than 1 second (60 per minute = 1/sec)

        # Second call should not wait
        wait = limiter.next()
        assert wait == 0

    def test_logger_called_when_waiting(self):
        """Test logger is called when waiting."""
        mock_logger = Mock()
        limiter = RateLimiter(per_minute=120, lg=mock_logger)

        # First call
        limiter.next()

        # Second call should log
        limiter.next()

        # Logger should have been called
        mock_logger.trace.assert_called_once()
        args, kwargs = mock_logger.trace.call_args
        assert "rate limiter wait" in args
        assert "extra" in kwargs
        assert "wait" in kwargs["extra"]

    def test_logger_not_called_without_wait(self):
        """Test logger not called when not waiting."""
        mock_logger = Mock()
        limiter = RateLimiter(per_minute=60, lg=mock_logger)

        # First call - no wait
        limiter.next()

        # Logger should not have been called
        mock_logger.trace.assert_not_called()


# =============================================================================
# Test Rate Limiting Calculations
# =============================================================================


@pytest.mark.unit
class TestRateLimitingCalculations:
    """Test rate limiting calculations."""

    def test_60_per_minute_delay(self):
        """Test 60 per minute gives 1 second delay."""
        limiter = RateLimiter(per_minute=60)
        delay = 60.0 / limiter.per_minute
        assert delay == 1.0

    def test_120_per_minute_delay(self):
        """Test 120 per minute gives 0.5 second delay."""
        limiter = RateLimiter(per_minute=120)
        delay = 60.0 / limiter.per_minute
        assert delay == 0.5

    def test_30_per_minute_delay(self):
        """Test 30 per minute gives 2 second delay."""
        limiter = RateLimiter(per_minute=30)
        delay = 60.0 / limiter.per_minute
        assert delay == 2.0


# =============================================================================
# Test Integration Scenarios
# =============================================================================


@pytest.mark.integration
class TestRateLimiterIntegration:
    """Test real-world rate limiter scenarios."""

    def test_rate_limiter_workflow(self):
        """Test complete rate limiter workflow."""
        limiter = RateLimiter(per_minute=120)  # Fast rate for testing

        # First operation - no wait
        wait1 = limiter.next()
        assert wait1 == 0

        # Second operation - should wait
        wait2 = limiter.next()
        assert wait2 > 0

        # Third operation - should wait
        wait3 = limiter.next()
        assert wait3 > 0

    def test_rate_limiter_with_variable_delays(self):
        """Test rate limiter with variable delays between calls."""
        limiter = RateLimiter(per_minute=120)

        limiter.next()
        time.sleep(0.3)  # Partial delay

        wait = limiter.next()
        # Should wait for remaining time
        assert 0 < wait < 0.5

    def test_multiple_operations_stay_within_rate(self):
        """Test multiple operations stay within rate limit."""
        limiter = RateLimiter(per_minute=120)  # 2 per second

        start = time.monotonic()

        # Perform 10 operations
        for _ in range(10):
            limiter.next()

        elapsed = time.monotonic() - start

        # Should take at least 4.5 seconds (10 ops / 2 per sec = 5 sec, minus first op)
        assert elapsed >= 4.0  # Allow some tolerance
