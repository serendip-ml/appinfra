# Time & Scheduling

Periodic task execution, scheduling, and time utilities.

## Ticker

Periodic task execution with configurable intervals. Supports three usage patterns: callback-based,
iterator, and iterator with context manager.

```python
class Ticker:
    def __init__(
        self,
        lg: Logger,                                    # Logger instance
        handler: TickerHandler | Callable | None = None,  # Optional for iterator mode
        secs: float | None = None,                     # Seconds between ticks
        initial: bool = True                           # Run initial tick immediately
    ): ...

    # Callback mode
    def run(self) -> None: ...       # Start ticker (blocking, requires handler)
    def stop(self) -> None: ...      # Stop ticker gracefully
    def is_running(self) -> bool: ...

    # Context manager (installs signal handlers)
    def __enter__(self) -> Ticker: ...
    def __exit__(self, *args) -> None: ...

    # Iterator (yields tick count)
    def __iter__(self) -> Iterator[int]: ...
```

**Iterator Pattern (Recommended):**

```python
from appinfra.time import Ticker

# With context manager - handles SIGTERM/SIGINT gracefully
with Ticker(lg, secs=5.0) as ticker:
    for tick in ticker:
        print(f"Tick {tick}")
        do_work()
        # Stops on SIGTERM/SIGINT

# Without context manager (manual stop required)
ticker = Ticker(lg, secs=5.0)
for tick in ticker:
    do_work()
    if done:
        ticker.stop()
```

**With Subprocess Context:**

```python
from appinfra.time import Ticker

def worker_process(app):
    with app.subprocess_context() as ctx:
        with Ticker(ctx.lg, secs=30) as ticker:
            for tick in ticker:
                sync_data()
                # Config hot-reload + signal handling
```

**Callback Pattern (Simple Callable):**

```python
from appinfra.time import Ticker

def my_task():
    print("Task executed!")

ticker = Ticker(lg, my_task, secs=5.0)
ticker.run()  # Blocks, executes my_task every 5 seconds
```

**Callback Pattern (Handler Class):**

```python
from appinfra.time import Ticker, TickerHandler

class MyHandler(TickerHandler):
    def ticker_start(self, *args, **kwargs):
        print("Ticker starting...")

    def ticker_tick(self):
        print("Tick!")

    def ticker_stop(self):
        print("Ticker stopping...")

handler = MyHandler()
ticker = Ticker(lg, handler, secs=2.0)
ticker.run()
```

**Running in Background Thread:**

```python
import threading

ticker = Ticker(lg, handler, secs=10.0)
thread = threading.Thread(target=ticker.run, daemon=True)
thread.start()

# Later...
ticker.stop()
```

## Sched (Scheduler)

Scheduled task execution at specific times (daily, weekly, monthly, hourly, minutely).

```python
class Sched:
    def __init__(
        self,
        lg: Logger,               # Logger instance
        period: str | Period,     # DAILY, WEEKLY, MONTHLY, HOURLY, MINUTELY
        when: str,                # Time spec: "HH:MM" or offset for hourly/minutely
        weekday: int | None = None,  # For WEEKLY (0=Monday, 6=Sunday)
        sleep_interval: int = 10  # Seconds between checks
    ): ...

    def run(self, msg_intvl_secs=3600, instant=False) -> Generator[float]: ...
    def sync(self, instant=False) -> tuple[bool, float]: ...
    def stop(self) -> None: ...
    def get_status(self) -> dict: ...

    # Properties
    next_t: float | None     # Next execution timestamp
    period: Period           # Scheduling period
    is_running: bool         # Whether scheduler is running
```

**Daily Execution:**

```python
import logging
from appinfra.time import Sched, Period

lg = logging.getLogger(__name__)

# Daily at 3:00 AM
sched = Sched(lg, Period.DAILY, "03:00")

for timestamp in sched.run():
    print(f"Executed at {timestamp}")
    generate_daily_report()
```

**Weekly Execution:**

```python
from appinfra.time import Sched, Period

# Weekly on Monday at 9:00 AM
sched = Sched(lg, Period.WEEKLY, "09:00", weekday=0)

for timestamp in sched.run():
    run_weekly_backup()
```

**Hourly/Minutely Execution:**

```python
from appinfra.time import Sched, Period

# Every hour at 15 minutes past
sched = Sched(lg, Period.HOURLY, "15")

# Every minute at 30 seconds past
sched = Sched(lg, Period.MINUTELY, "30")
```

**With Context Manager:**

```python
with Sched(lg, Period.HOURLY, "30") as sched:
    for timestamp in sched.run():
        collect_metrics()
        # sched.stop() called automatically on exit
```

**Manual Sync (Non-blocking):**

```python
sched = Sched(lg, Period.DAILY, "09:00")

while True:
    triggered, delay = sched.sync()
    if triggered:
        run_task()
    time.sleep(1)
```

## ETA (Progress Tracking)

Estimated time to completion using EWMA-smoothed rate calculation.

```python
class ETA:
    def __init__(
        self,
        total: float = 100.0,   # Total units (default 100 for percentage)
        age: float = 30.0       # EWMA smoothing parameter
    ): ...

    def update(self, completed: float) -> None: ...   # Update progress (absolute, not delta)
    def remaining_secs(self) -> float | None: ...     # Estimated seconds remaining
    def rate(self) -> float: ...                      # Current rate (units/sec)
    def percent(self) -> float: ...                   # Completion percentage (0-100)
```

**Basic Usage (Item Count):**

```python
from appinfra.time import ETA

# Track progress of 1000 items
eta = ETA(total=1000)
for i, item in enumerate(items):
    process(item)
    eta.update(i + 1)

    remaining = eta.remaining_secs()
    if remaining is not None:
        print(f"{eta.percent():.1f}% - {remaining:.0f}s remaining")
```

**Percentage-Based Tracking:**

```python
from appinfra.time import ETA

# Default total=100 for percentage tracking
eta = ETA()
eta.update(25.0)  # 25% complete
eta.update(50.0)  # 50% complete

print(f"Rate: {eta.rate():.1f} %/sec")
print(f"ETA: {eta.remaining_secs():.0f}s")
```

**With Custom Smoothing:**

```python
# Lower age = faster response to rate changes (noisier)
eta = ETA(total=1000, age=10.0)

# Higher age = smoother estimates (slower to react)
eta = ETA(total=1000, age=60.0)
```

**Notes:**
- `update()` takes absolute progress, not deltas
- `remaining_secs()` returns `None` until rate can be calculated
- Handles variable update intervals automatically

## Duration Formatting

```python
from appinfra.time import delta_str, delta_to_secs

# Format seconds to string
print(delta_str(3661))          # "1h1m1s"
print(delta_str(90.123))        # "1m30s"
print(delta_str(9.123))         # "9.123s"

# Full precision mode
print(delta_str(3661.5, precise=True))  # "1h01m01.500s"

# Different formats
print(delta_str(3661, format="short"))  # "1h1m1s"
print(delta_str(3661, format="long"))   # "1 hour 1 minute 1 second"

# Parse duration string to seconds
seconds = delta_to_secs("1h 30m")  # 5400
seconds = delta_to_secs("2d")      # 172800
```

## Date Iteration

```python
from appinfra.time import iter_dates
from datetime import date

# Iterate over date range (memory-efficient)
for d in iter_dates(date(2025, 12, 1), date(2025, 12, 10)):
    print(d)  # 2025-12-01, 2025-12-02, ...
```

## Duration Validation

```python
from appinfra.time import validate_duration, InvalidDurationError

try:
    validate_duration("1h 30m")  # Valid
    validate_duration("invalid")  # Raises InvalidDurationError
except InvalidDurationError as e:
    print(f"Invalid duration: {e}")
```

## Period Enum

```python
from appinfra.time import Period

Period.MINUTELY  # Every minute
Period.HOURLY    # Every hour
Period.DAILY     # Every day
Period.WEEKLY    # Every week
Period.MONTHLY   # Every month
```

## See Also

- [Application Framework](app.md) - Use with app lifecycle
- [Hot-Reload Logging](../guides/hot-reload-logging.md) - Using Ticker with subprocess context
