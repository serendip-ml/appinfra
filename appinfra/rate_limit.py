"""
Rate limiting functionality for controlling request frequency.

This module provides a RateLimiter class for implementing rate limiting
to control the frequency of operations or API calls.
"""

import time
from typing import Any

from . import time as t


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
