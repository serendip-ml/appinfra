"""
Rate limiting functionality for controlling request frequency.

This module provides a RateLimiter class for implementing rate limiting
to control the frequency of operations or API calls, and a Backoff class
for implementing exponential backoff retry logic.
"""

import random
import time
from typing import Any

from . import time as t
from .log import Logger


class RateLimiter:
    """
    Rate limiter for controlling operation frequency.

    Provides functionality to limit the rate of operations to a specified
    number per minute, with automatic waiting when the rate limit is exceeded.
    """

    def __init__(self, per_minute: int, lg: Any | None = None) -> None:
        """
        Initialize the rate limiter.

        Args:
            per_minute (int): Maximum number of operations per minute
            lg: Logger instance for rate limiting operations (optional)
        """
        self.per_minute = per_minute
        self.last_t: float | None = None
        self._lg = lg

    def next(self, respect_max_ticks: bool = True) -> float:
        """
        Wait for the next allowed operation time.

        Calculates the required delay based on the rate limit and sleeps
        if necessary to maintain the specified rate.

        Args:
            respect_max_ticks (bool): Whether to respect the rate limit

        Returns:
            float: Time waited in seconds
        """
        delay = 60.0 / self.per_minute
        now = time.monotonic()
        wait = 0.0
        if self.last_t is not None:
            delta = now - self.last_t
            if delta < delay:
                wait = delay - delta
                if respect_max_ticks:
                    if self._lg:
                        self._lg.trace(
                            "rate limiter wait",
                            extra={"wait": t.delta.delta_str(wait, precise=False)},
                        )
                    time.sleep(wait)
        self.last_t = time.monotonic()
        return wait

    def try_next(self) -> bool:
        """
        Non-blocking rate limit check.

        Checks if the rate limit allows an operation without blocking.
        If allowed, updates the last operation time and returns True.
        If rate limited, returns False without modifying state.

        This method is useful for event loops that cannot block, such as
        message-processing loops that need to handle signals while rate-limiting
        operations.

        Returns:
            bool: True if operation is allowed (updates last_t), False if rate limited.

        Example:
            if limiter.try_next():
                do_operation()
            else:
                # Skip this cycle, will retry on next loop iteration
                pass
        """
        delay = 60.0 / self.per_minute
        now = time.monotonic()
        if self.last_t is None or (now - self.last_t) >= delay:
            self.last_t = now
            return True
        return False


class Backoff:
    """
    Exponential backoff for retry logic.

    Provides functionality to implement exponential backoff when retrying
    failed operations, with configurable base delay, maximum delay, growth
    factor, and optional jitter to avoid thundering herd problems.
    """

    def __init__(
        self,
        lg: Logger,
        base: float = 1.0,
        max_delay: float = 60.0,
        factor: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize the backoff controller.

        Args:
            lg: Logger instance for backoff operations
            base: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay cap in seconds (default: 60.0)
            factor: Multiplier applied per attempt (default: 2.0)
            jitter: Whether to randomize delays to avoid thundering herd (default: True)
        """
        self._lg = lg
        self.base = base
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter
        self._attempts = 0

    @property
    def attempts(self) -> int:
        """Return the current attempt count."""
        return self._attempts

    def next_delay(self) -> float:
        """
        Calculate the next backoff delay and increment attempt count.

        The delay is calculated as: min(base * (factor ** attempts), max_delay)
        If jitter is enabled, the delay is multiplied by a random factor
        between 0.5 and 1.0 (full jitter pattern).

        Returns:
            float: The calculated delay in seconds.
        """
        delay = min(self.base * (self.factor**self._attempts), self.max_delay)
        if self.jitter:
            delay = delay * random.uniform(0.5, 1.0)
        self._attempts += 1
        return delay

    def wait(self) -> float:
        """
        Wait for the calculated backoff delay.

        Calculates the next delay using next_delay(), sleeps for that duration,
        and returns the actual delay.

        Returns:
            float: The actual delay waited in seconds.
        """
        delay = self.next_delay()
        self._lg.trace(
            "backoff wait",
            extra={
                "delay": t.delta.delta_str(delay, precise=False),
                "attempt": self._attempts,
            },
        )
        time.sleep(delay)
        return delay

    def reset(self) -> None:
        """Reset the attempt counter after a successful operation."""
        self._attempts = 0
